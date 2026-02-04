"""API routes for analytics zones (line zones and polygon zones).

This module provides CRUD endpoints for managing analytics zones:
- Line zones: Virtual tripwires for counting and detecting line crossings
- Polygon zones: Region-based intrusion detection and object counting
- Dwell time tracking: Monitor how long objects stay in polygon zones

Analytics zones are camera-specific and can be configured per camera to define
areas of interest for automated analytics.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import ORJSONResponse, RedirectResponse

from backend.api.dependencies import DbSession, get_camera_or_404
from backend.api.schemas.analytics_zone import (
    ApproachUrgency,
    ApproachVectorData,
    CameraApproachVectorsResponse,
    EntityTypeCount,
    LineZoneCreate,
    LineZoneListResponse,
    LineZoneResponse,
    LineZoneUpdate,
    PolygonZoneCreate,
    PolygonZoneListResponse,
    PolygonZoneResponse,
    PolygonZoneUpdate,
    ZoneApproachVectorsResponse,
    ZoneEntityDistribution,
    ZoneEntityDistributionResponse,
)
from backend.api.schemas.dwell_time import (
    ActiveDwellerResponse,
    ActiveDwellersListResponse,
    DwellHistoryResponse,
    DwellStatisticsResponse,
    DwellTimeRecordResponse,
    LoiteringCheckRequest,
    LoiteringCheckResponse,
)
from backend.api.schemas.line_zone_analytics import CrossingTrendsResponse
from backend.api.schemas.loitering_config import (
    LoiteringConfigResponse,
    LoiteringConfigUpdate,
)
from backend.api.schemas.zone_activity_heatmap import (
    HeatmapDataPoint,
    HeatmapTimeRange,
    HourlyActivity,
    ZoneActivityHeatmapResponse,
)
from backend.api.schemas.zone_comparison import (
    ComparisonMetric,
    ComparisonPeriod,
    ZoneComparisonData,
    ZoneComparisonResponse,
)
from backend.core.logging import get_logger
from backend.core.time_utils import utc_now
from backend.services.dwell_time_service import get_dwell_time_service
from backend.services.line_zone_service import get_line_zone_service
from backend.services.polygon_zone_service import get_polygon_zone_service

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/analytics-zones",
    tags=["analytics-zones"],
    default_response_class=ORJSONResponse,
)

# Redirect router for /api/zones -> /api/analytics-zones (NEM-5377)
# This provides backward compatibility for clients using the old /api/zones path
zones_redirect_router = APIRouter(
    prefix="/api/zones",
    tags=["analytics-zones"],
    include_in_schema=False,  # Hide from OpenAPI docs since it's just a redirect
)


@zones_redirect_router.api_route(
    "",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
    include_in_schema=False,
)
@zones_redirect_router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
    include_in_schema=False,
)
async def zones_redirect(request: Request, path: str = "") -> RedirectResponse:
    """Redirect /api/zones requests to /api/analytics-zones.

    This redirect provides backward compatibility for clients that may be
    using the old /api/zones path. All requests are redirected with HTTP 308
    Permanent Redirect to preserve the request method.

    Args:
        request: The incoming request (used to preserve query string).
        path: Optional path suffix to append to the redirect URL.

    Returns:
        RedirectResponse with HTTP 308 status to /api/analytics-zones/{path}.
    """
    # Build redirect URL with path and query string
    redirect_url = f"/api/analytics-zones/{path}" if path else "/api/analytics-zones/"
    if request.url.query:
        redirect_url = f"{redirect_url}?{request.url.query}"

    logger.debug(
        f"Redirecting {request.method} {request.url.path} -> {redirect_url}",
        extra={"original_path": str(request.url.path), "redirect_url": redirect_url},
    )

    return RedirectResponse(url=redirect_url, status_code=status.HTTP_308_PERMANENT_REDIRECT)


# ============================================================================
# Line Zone Endpoints
# ============================================================================


@router.post(
    "/line-zones",
    response_model=LineZoneResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new line zone",
    responses={
        201: {"description": "Line zone created successfully"},
        404: {"description": "Camera not found"},
    },
)
async def create_line_zone(
    data: LineZoneCreate,
    db: DbSession,
) -> LineZoneResponse:
    """Create a new line zone for a camera.

    Line zones are virtual tripwires that detect and count objects
    crossing from one side to the other. They are defined by start
    and end coordinates (in pixels).

    Args:
        data: Line zone creation data including camera_id and coordinates.
        db: Database session.

    Returns:
        The created LineZone with initial counts set to zero.

    Raises:
        HTTPException: 404 if camera not found.
    """
    # Verify camera exists
    await get_camera_or_404(data.camera_id, db)

    service = get_line_zone_service(db)
    zone = await service.create_zone(camera_id=data.camera_id, data=data)
    await db.commit()

    logger.info(
        f"Created line zone '{zone.name}' for camera {data.camera_id}",
        extra={"zone_id": zone.id, "camera_id": data.camera_id},
    )

    return LineZoneResponse.model_validate(zone)


@router.get(
    "/line-zones/{zone_id}",
    response_model=LineZoneResponse,
    summary="Get a line zone by ID",
    responses={
        200: {"description": "Line zone retrieved successfully"},
        404: {"description": "Line zone not found"},
    },
)
async def get_line_zone(
    zone_id: int,
    db: DbSession,
) -> LineZoneResponse:
    """Get a line zone by ID.

    Args:
        zone_id: The unique identifier of the line zone.
        db: Database session.

    Returns:
        The LineZone with current crossing counts.

    Raises:
        HTTPException: 404 if line zone not found.
    """
    service = get_line_zone_service(db)
    zone = await service.get_zone(zone_id)

    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Line zone with id {zone_id} not found",
        )

    return LineZoneResponse.model_validate(zone)


@router.get(
    "/line-zones/camera/{camera_id}",
    response_model=LineZoneListResponse,
    summary="Get all line zones for a camera",
    responses={
        200: {"description": "Line zones retrieved successfully"},
        404: {"description": "Camera not found"},
    },
)
async def get_line_zones_by_camera(
    camera_id: str,
    db: DbSession,
) -> LineZoneListResponse:
    """Get all line zones for a camera.

    Args:
        camera_id: ID of the camera to get zones for.
        db: Database session.

    Returns:
        List of LineZone objects for the camera.

    Raises:
        HTTPException: 404 if camera not found.
    """
    # Verify camera exists
    await get_camera_or_404(camera_id, db)

    service = get_line_zone_service(db)
    zones = await service.get_zones_by_camera(camera_id)

    return LineZoneListResponse(
        zones=[LineZoneResponse.model_validate(z) for z in zones],
        total=len(zones),
    )


@router.patch(
    "/line-zones/{zone_id}",
    response_model=LineZoneResponse,
    summary="Update a line zone",
    responses={
        200: {"description": "Line zone updated successfully"},
        404: {"description": "Line zone not found"},
    },
)
async def update_line_zone(
    zone_id: int,
    data: LineZoneUpdate,
    db: DbSession,
) -> LineZoneResponse:
    """Update a line zone.

    Only the fields present in the request body are updated.

    Args:
        zone_id: ID of the line zone to update.
        data: Update data with optional fields.
        db: Database session.

    Returns:
        The updated LineZone.

    Raises:
        HTTPException: 404 if line zone not found.
    """
    service = get_line_zone_service(db)
    zone = await service.update_zone(zone_id, data)

    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Line zone with id {zone_id} not found",
        )

    await db.commit()

    logger.info(
        f"Updated line zone {zone_id}",
        extra={"zone_id": zone_id},
    )

    return LineZoneResponse.model_validate(zone)


@router.delete(
    "/line-zones/{zone_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a line zone",
    responses={
        204: {"description": "Line zone deleted successfully"},
        404: {"description": "Line zone not found"},
    },
)
async def delete_line_zone(
    zone_id: int,
    db: DbSession,
) -> None:
    """Delete a line zone.

    Args:
        zone_id: ID of the line zone to delete.
        db: Database session.

    Raises:
        HTTPException: 404 if line zone not found.
    """
    service = get_line_zone_service(db)
    deleted = await service.delete_zone(zone_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Line zone with id {zone_id} not found",
        )

    await db.commit()

    logger.info(
        f"Deleted line zone {zone_id}",
        extra={"zone_id": zone_id},
    )


@router.post(
    "/line-zones/{zone_id}/reset-counts",
    response_model=LineZoneResponse,
    summary="Reset crossing counts for a line zone",
    responses={
        200: {"description": "Counts reset successfully"},
        404: {"description": "Line zone not found"},
    },
)
async def reset_line_zone_counts(
    zone_id: int,
    db: DbSession,
) -> LineZoneResponse:
    """Reset crossing counts for a line zone.

    Sets both in_count and out_count to zero.

    Args:
        zone_id: ID of the line zone.
        db: Database session.

    Returns:
        The LineZone with reset counts.

    Raises:
        HTTPException: 404 if line zone not found.
    """
    service = get_line_zone_service(db)

    # Check zone exists first
    zone = await service.get_zone(zone_id)
    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Line zone with id {zone_id} not found",
        )

    await service.reset_counts(zone_id)
    await db.commit()

    # Refresh zone to get updated counts
    zone = await service.get_zone(zone_id)

    logger.info(
        f"Reset counts for line zone {zone_id}",
        extra={"zone_id": zone_id},
    )

    return LineZoneResponse.model_validate(zone)


@router.get(
    "/line-zones/{zone_id}/crossing-trends",
    response_model=CrossingTrendsResponse,
    summary="Get crossing trends for a line zone",
    responses={
        200: {"description": "Crossing trends retrieved successfully"},
        404: {"description": "Line zone not found"},
    },
)
async def get_crossing_trends(
    zone_id: int,
    db: DbSession,
    start_time: datetime | None = Query(
        default=None,
        description="Start of time window (defaults to 24 hours ago)",
    ),
    end_time: datetime | None = Query(
        default=None,
        description="End of time window (defaults to now)",
    ),
    interval: str = Query(
        default="hour",
        description="Aggregation interval: 'hour' or 'day'",
    ),
) -> CrossingTrendsResponse:
    """Get crossing trends for a line zone.

    Returns time-bucketed crossing data for the specified time range.
    By default, retrieves the last 24 hours of data aggregated by hour.

    Note: Currently returns cumulative counts as a single data point since
    individual crossing events are not stored. Future versions will support
    true historical trend data.

    Args:
        zone_id: ID of the line zone.
        db: Database session.
        start_time: Start of the time window (defaults to 24 hours ago).
        end_time: End of the time window (defaults to now).
        interval: Aggregation interval ('hour' or 'day').

    Returns:
        Crossing trends with time-bucketed data points.

    Raises:
        HTTPException: 404 if line zone not found.
    """
    # Default time window: last 24 hours
    now = utc_now()
    actual_end = end_time or now
    actual_start = start_time or (now - timedelta(hours=24))

    service = get_line_zone_service(db)
    trends = await service.get_crossing_trends(
        zone_id=zone_id,
        start_time=actual_start,
        end_time=actual_end,
        interval=interval,
    )

    if trends is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Line zone with id {zone_id} not found",
        )

    logger.debug(
        f"Retrieved crossing trends for zone {zone_id}",
        extra={
            "zone_id": zone_id,
            "start_time": actual_start.isoformat(),
            "end_time": actual_end.isoformat(),
            "interval": interval,
        },
    )

    return trends


# ============================================================================
# Polygon Zone Endpoints
# ============================================================================


@router.post(
    "/polygon-zones",
    response_model=PolygonZoneResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new polygon zone",
    responses={
        201: {"description": "Polygon zone created successfully"},
        404: {"description": "Camera not found"},
    },
)
async def create_polygon_zone(
    data: PolygonZoneCreate,
    db: DbSession,
) -> PolygonZoneResponse:
    """Create a new polygon zone for a camera.

    Polygon zones monitor activity within defined areas.
    Supports various zone types for different monitoring scenarios.

    Args:
        data: Polygon zone creation data including camera_id and polygon.
        db: Database session.

    Returns:
        The created PolygonZone with initial count set to zero.

    Raises:
        HTTPException: 404 if camera not found.
    """
    # Verify camera exists
    await get_camera_or_404(data.camera_id, db)

    service = get_polygon_zone_service(db)
    zone = await service.create_zone(camera_id=data.camera_id, data=data)
    await db.commit()

    logger.info(
        f"Created polygon zone '{zone.name}' for camera {data.camera_id}",
        extra={"zone_id": zone.id, "camera_id": data.camera_id},
    )

    return PolygonZoneResponse.model_validate(zone)


@router.get(
    "/polygon-zones/{zone_id}",
    response_model=PolygonZoneResponse,
    summary="Get a polygon zone by ID",
    responses={
        200: {"description": "Polygon zone retrieved successfully"},
        404: {"description": "Polygon zone not found"},
    },
)
async def get_polygon_zone(
    zone_id: int,
    db: DbSession,
) -> PolygonZoneResponse:
    """Get a polygon zone by ID.

    Args:
        zone_id: The unique identifier of the polygon zone.
        db: Database session.

    Returns:
        The PolygonZone with current object count.

    Raises:
        HTTPException: 404 if polygon zone not found.
    """
    service = get_polygon_zone_service(db)
    zone = await service.get_zone(zone_id)

    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Polygon zone with id {zone_id} not found",
        )

    return PolygonZoneResponse.model_validate(zone)


@router.get(
    "/polygon-zones/camera/{camera_id}",
    response_model=PolygonZoneListResponse,
    summary="Get all polygon zones for a camera",
    responses={
        200: {"description": "Polygon zones retrieved successfully"},
        404: {"description": "Camera not found"},
    },
)
async def get_polygon_zones_by_camera(
    camera_id: str,
    db: DbSession,
    active_only: bool = Query(
        default=True,
        description="If True, only return active zones. If False, return all zones.",
    ),
) -> PolygonZoneListResponse:
    """Get all polygon zones for a camera.

    Args:
        camera_id: ID of the camera to get zones for.
        db: Database session.
        active_only: If True, only return zones where is_active=True.
            Defaults to True.

    Returns:
        List of PolygonZone objects for the camera.

    Raises:
        HTTPException: 404 if camera not found.
    """
    # Verify camera exists
    await get_camera_or_404(camera_id, db)

    service = get_polygon_zone_service(db)
    zones = await service.get_zones_by_camera(camera_id, active_only=active_only)

    return PolygonZoneListResponse(
        zones=[PolygonZoneResponse.model_validate(z) for z in zones],
        total=len(zones),
    )


@router.patch(
    "/polygon-zones/{zone_id}",
    response_model=PolygonZoneResponse,
    summary="Update a polygon zone",
    responses={
        200: {"description": "Polygon zone updated successfully"},
        404: {"description": "Polygon zone not found"},
    },
)
async def update_polygon_zone(
    zone_id: int,
    data: PolygonZoneUpdate,
    db: DbSession,
) -> PolygonZoneResponse:
    """Update a polygon zone.

    Only the fields present in the request body are updated.

    Args:
        zone_id: ID of the polygon zone to update.
        data: Update data with optional fields.
        db: Database session.

    Returns:
        The updated PolygonZone.

    Raises:
        HTTPException: 404 if polygon zone not found.
    """
    service = get_polygon_zone_service(db)
    zone = await service.update_zone(zone_id, data)

    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Polygon zone with id {zone_id} not found",
        )

    await db.commit()

    logger.info(
        f"Updated polygon zone {zone_id}",
        extra={"zone_id": zone_id},
    )

    return PolygonZoneResponse.model_validate(zone)


@router.delete(
    "/polygon-zones/{zone_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a polygon zone",
    responses={
        204: {"description": "Polygon zone deleted successfully"},
        404: {"description": "Polygon zone not found"},
    },
)
async def delete_polygon_zone(
    zone_id: int,
    db: DbSession,
) -> None:
    """Delete a polygon zone.

    Args:
        zone_id: ID of the polygon zone to delete.
        db: Database session.

    Raises:
        HTTPException: 404 if polygon zone not found.
    """
    service = get_polygon_zone_service(db)
    deleted = await service.delete_zone(zone_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Polygon zone with id {zone_id} not found",
        )

    await db.commit()

    logger.info(
        f"Deleted polygon zone {zone_id}",
        extra={"zone_id": zone_id},
    )


@router.post(
    "/polygon-zones/{zone_id}/toggle-active",
    response_model=PolygonZoneResponse,
    summary="Toggle the active status of a polygon zone",
    responses={
        200: {"description": "Active status toggled successfully"},
        404: {"description": "Polygon zone not found"},
    },
)
async def toggle_polygon_zone_active(
    zone_id: int,
    db: DbSession,
) -> PolygonZoneResponse:
    """Toggle the active status of a polygon zone.

    Toggles is_active between True and False.

    Args:
        zone_id: ID of the polygon zone.
        db: Database session.

    Returns:
        The PolygonZone with updated active status.

    Raises:
        HTTPException: 404 if polygon zone not found.
    """
    service = get_polygon_zone_service(db)

    # Get current zone
    zone = await service.get_zone(zone_id)
    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Polygon zone with id {zone_id} not found",
        )

    # Toggle active status
    new_status = not zone.is_active
    zone = await service.set_active(zone_id, new_status)
    await db.commit()

    logger.info(
        f"Toggled polygon zone {zone_id} active status to {new_status}",
        extra={"zone_id": zone_id, "is_active": new_status},
    )

    return PolygonZoneResponse.model_validate(zone)


# ============================================================================
# Dwell Time Endpoints
# ============================================================================


async def _get_polygon_zone_or_404(zone_id: int, db: DbSession) -> None:
    """Verify polygon zone exists, raise 404 if not found."""
    service = get_polygon_zone_service(db)
    zone = await service.get_zone(zone_id)
    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Polygon zone with id {zone_id} not found",
        )


@router.get(
    "/polygon-zones/{zone_id}/dwellers",
    response_model=ActiveDwellersListResponse,
    summary="Get active dwellers in a polygon zone",
    responses={
        200: {"description": "Active dwellers retrieved successfully"},
        404: {"description": "Polygon zone not found"},
    },
)
async def get_active_dwellers(
    zone_id: int,
    db: DbSession,
) -> ActiveDwellersListResponse:
    """Get all objects currently dwelling in a polygon zone.

    Returns objects that have entered the zone but have not yet exited.
    Each object includes the current dwell time calculated at request time.

    Args:
        zone_id: ID of the polygon zone.
        db: Database session.

    Returns:
        List of active dwellers with current dwell times.

    Raises:
        HTTPException: 404 if polygon zone not found.
    """
    # Verify zone exists
    await _get_polygon_zone_or_404(zone_id, db)

    dwell_service = get_dwell_time_service(db)
    records = await dwell_service.get_active_dwellers(zone_id)

    now = utc_now()
    dwellers = [
        ActiveDwellerResponse(
            record_id=record.id,
            track_id=record.track_id,
            camera_id=record.camera_id,
            object_class=record.object_class,
            entry_time=record.entry_time,
            current_dwell_seconds=record.calculate_dwell_time(now),
        )
        for record in records
    ]

    logger.debug(
        f"Retrieved {len(dwellers)} active dwellers for zone {zone_id}",
        extra={"zone_id": zone_id, "count": len(dwellers)},
    )

    return ActiveDwellersListResponse(
        zone_id=zone_id,
        dwellers=dwellers,
        total=len(dwellers),
    )


@router.get(
    "/polygon-zones/{zone_id}/dwell-history",
    response_model=DwellHistoryResponse,
    summary="Get dwell time history for a polygon zone",
    responses={
        200: {"description": "Dwell history retrieved successfully"},
        404: {"description": "Polygon zone not found"},
    },
)
async def get_dwell_history(
    zone_id: int,
    db: DbSession,
    start_time: datetime | None = Query(
        default=None,
        description="Start of time window (defaults to 24 hours ago)",
    ),
    end_time: datetime | None = Query(
        default=None,
        description="End of time window (defaults to now)",
    ),
    include_active: bool = Query(
        default=True,
        description="Whether to include currently active dwellers",
    ),
) -> DwellHistoryResponse:
    """Get historical dwell time records for a polygon zone.

    Returns all dwell time records that overlap with the specified time window.
    By default, retrieves the last 24 hours of data.

    Args:
        zone_id: ID of the polygon zone.
        db: Database session.
        start_time: Start of the time window (defaults to 24 hours ago).
        end_time: End of the time window (defaults to now).
        include_active: Whether to include currently active records.

    Returns:
        Historical dwell time records.

    Raises:
        HTTPException: 404 if polygon zone not found.
    """
    # Verify zone exists
    await _get_polygon_zone_or_404(zone_id, db)

    # Default time window: last 24 hours
    now = utc_now()
    actual_end = end_time or now
    actual_start = start_time or (now - timedelta(hours=24))

    dwell_service = get_dwell_time_service(db)
    records = await dwell_service.get_dwell_history(
        zone_id=zone_id,
        start_time=actual_start,
        end_time=actual_end,
        include_active=include_active,
    )

    logger.debug(
        f"Retrieved {len(records)} dwell records for zone {zone_id}",
        extra={
            "zone_id": zone_id,
            "count": len(records),
            "start_time": actual_start.isoformat(),
            "end_time": actual_end.isoformat(),
        },
    )

    return DwellHistoryResponse(
        zone_id=zone_id,
        records=[
            DwellTimeRecordResponse(
                id=r.id,
                zone_id=r.zone_id,
                track_id=r.track_id,
                camera_id=r.camera_id,
                object_class=r.object_class,
                entry_time=r.entry_time,
                exit_time=r.exit_time,
                total_seconds=r.total_seconds,
                triggered_alert=r.triggered_alert,
                is_active=r.is_active,
            )
            for r in records
        ],
        total=len(records),
        start_time=actual_start,
        end_time=actual_end,
    )


@router.post(
    "/polygon-zones/{zone_id}/check-loitering",
    response_model=LoiteringCheckResponse,
    summary="Check for loitering in a polygon zone",
    responses={
        200: {"description": "Loitering check completed successfully"},
        404: {"description": "Polygon zone not found"},
    },
)
async def check_loitering(
    zone_id: int,
    request: LoiteringCheckRequest,
    db: DbSession,
) -> LoiteringCheckResponse:
    """Check for loitering in a polygon zone.

    Identifies objects that have been dwelling in the zone longer than
    the specified threshold. Returns alerts for all objects exceeding
    the threshold, marking them as triggered in the database.

    Args:
        zone_id: ID of the polygon zone.
        request: Loitering check request with threshold.
        db: Database session.

    Returns:
        Loitering alerts for objects exceeding the threshold.

    Raises:
        HTTPException: 404 if polygon zone not found.
    """
    # Verify zone exists
    await _get_polygon_zone_or_404(zone_id, db)

    dwell_service = get_dwell_time_service(db)
    alerts = await dwell_service.check_loitering(
        zone_id=zone_id,
        threshold_seconds=request.threshold_seconds,
    )
    await db.commit()

    if alerts:
        logger.warning(
            f"Detected {len(alerts)} loitering alerts in zone {zone_id}",
            extra={
                "zone_id": zone_id,
                "alert_count": len(alerts),
                "threshold_seconds": request.threshold_seconds,
            },
        )

    return LoiteringCheckResponse(
        zone_id=zone_id,
        threshold_seconds=request.threshold_seconds,
        alerts=alerts,
        total_alerts=len(alerts),
    )


@router.get(
    "/polygon-zones/{zone_id}/dwell-statistics",
    response_model=DwellStatisticsResponse,
    summary="Get dwell time statistics for a polygon zone",
    responses={
        200: {"description": "Dwell statistics retrieved successfully"},
        404: {"description": "Polygon zone not found"},
    },
)
async def get_dwell_statistics(
    zone_id: int,
    db: DbSession,
    start_time: datetime | None = Query(
        default=None,
        description="Start of statistics window (defaults to 24 hours ago)",
    ),
    end_time: datetime | None = Query(
        default=None,
        description="End of statistics window (defaults to now)",
    ),
) -> DwellStatisticsResponse:
    """Get dwell time statistics for a polygon zone.

    Returns aggregated statistics including average, min, max dwell times
    and the number of loitering alerts triggered in the time window.

    Args:
        zone_id: ID of the polygon zone.
        db: Database session.
        start_time: Start of the statistics window (defaults to 24 hours ago).
        end_time: End of the statistics window (defaults to now).

    Returns:
        Dwell time statistics for the zone.

    Raises:
        HTTPException: 404 if polygon zone not found.
    """
    # Verify zone exists
    await _get_polygon_zone_or_404(zone_id, db)

    # Default time window: last 24 hours
    now = utc_now()
    actual_end = end_time or now
    actual_start = start_time or (now - timedelta(hours=24))

    dwell_service = get_dwell_time_service(db)
    stats = await dwell_service.get_zone_statistics(
        zone_id=zone_id,
        start_time=actual_start,
        end_time=actual_end,
    )

    logger.debug(
        f"Retrieved dwell statistics for zone {zone_id}",
        extra={
            "zone_id": zone_id,
            "total_records": stats["total_records"],
            "start_time": actual_start.isoformat(),
            "end_time": actual_end.isoformat(),
        },
    )

    return DwellStatisticsResponse(
        zone_id=zone_id,
        total_records=stats["total_records"],
        avg_dwell_seconds=stats["avg_dwell_seconds"],
        max_dwell_seconds=stats["max_dwell_seconds"],
        min_dwell_seconds=stats["min_dwell_seconds"],
        alerts_triggered=stats["alerts_triggered"],
        start_time=actual_start,
        end_time=actual_end,
    )


# ============================================================================
# Loitering Configuration Endpoints
# ============================================================================


@router.get(
    "/polygon-zones/{zone_id}/loitering-config",
    response_model=LoiteringConfigResponse,
    summary="Get loitering configuration for a polygon zone",
    responses={
        200: {"description": "Loitering configuration retrieved successfully"},
        404: {"description": "Polygon zone not found"},
    },
)
async def get_loitering_config(
    zone_id: int,
    db: DbSession,
) -> LoiteringConfigResponse:
    """Get the current loitering configuration for a polygon zone.

    Returns the loitering threshold and alert settings for the specified zone.
    Loitering detection identifies objects that remain in a zone longer than
    the configured threshold.

    Args:
        zone_id: ID of the polygon zone.
        db: Database session.

    Returns:
        Current loitering configuration for the zone.

    Raises:
        HTTPException: 404 if polygon zone not found.
    """
    service = get_polygon_zone_service(db)
    zone = await service.get_zone(zone_id)

    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Polygon zone with id {zone_id} not found",
        )

    logger.debug(
        f"Retrieved loitering config for zone {zone_id}",
        extra={
            "zone_id": zone_id,
            "threshold_seconds": zone.loitering_threshold_seconds,
            "alert_enabled": zone.loitering_alert_enabled,
        },
    )

    return LoiteringConfigResponse(
        zone_id=zone.id,
        zone_name=zone.name,
        threshold_seconds=zone.loitering_threshold_seconds,
        alert_enabled=zone.loitering_alert_enabled,
    )


@router.patch(
    "/polygon-zones/{zone_id}/loitering-config",
    response_model=LoiteringConfigResponse,
    summary="Update loitering configuration for a polygon zone",
    responses={
        200: {"description": "Loitering configuration updated successfully"},
        404: {"description": "Polygon zone not found"},
        422: {"description": "Validation error (e.g., threshold out of range)"},
    },
)
async def update_loitering_config(
    zone_id: int,
    config: LoiteringConfigUpdate,
    db: DbSession,
) -> LoiteringConfigResponse:
    """Update loitering threshold and alert settings for a polygon zone.

    Configures when loitering alerts are triggered based on how long an
    object remains in the zone.

    Args:
        zone_id: ID of the polygon zone.
        config: Loitering configuration update request.
        db: Database session.

    Returns:
        Updated loitering configuration for the zone.

    Raises:
        HTTPException: 404 if polygon zone not found.
        HTTPException: 422 if validation fails (threshold out of range).
    """
    service = get_polygon_zone_service(db)
    zone = await service.get_zone(zone_id)

    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Polygon zone with id {zone_id} not found",
        )

    # Update the zone
    zone.loitering_threshold_seconds = config.threshold_seconds
    zone.loitering_alert_enabled = config.alert_enabled
    await db.commit()
    await db.refresh(zone)

    logger.info(
        f"Updated loitering config for zone {zone_id}",
        extra={
            "zone_id": zone_id,
            "threshold_seconds": zone.loitering_threshold_seconds,
            "alert_enabled": zone.loitering_alert_enabled,
        },
    )

    return LoiteringConfigResponse(
        zone_id=zone.id,
        zone_name=zone.name,
        threshold_seconds=zone.loitering_threshold_seconds,
        alert_enabled=zone.loitering_alert_enabled,
    )


# ============================================================================
# Zone Comparison Endpoints
# ============================================================================


# ============================================================================
# Entity Distribution Endpoints (NEM-4937)
# ============================================================================


@router.get(
    "/polygon-zones/{zone_id}/entity-distribution",
    response_model=ZoneEntityDistribution,
    summary="Get entity type distribution for a polygon zone",
    responses={
        200: {"description": "Entity distribution retrieved successfully"},
        404: {"description": "Polygon zone not found"},
    },
)
async def get_zone_entity_distribution(
    zone_id: int,
    db: DbSession,
    start_time: datetime | None = Query(
        default=None,
        description="Start of time window (defaults to 24 hours ago)",
    ),
    end_time: datetime | None = Query(
        default=None,
        description="End of time window (defaults to now)",
    ),
) -> ZoneEntityDistribution:
    """Get entity type distribution for a polygon zone.

    Returns counts of each entity type (person, vehicle, etc.) that have
    been detected in the zone during the specified time window.

    Args:
        zone_id: ID of the polygon zone.
        db: Database session.
        start_time: Start of time window (defaults to 24 hours ago).
        end_time: End of time window (defaults to now).

    Returns:
        Entity distribution with counts and percentages per type.

    Raises:
        HTTPException: 404 if polygon zone not found.
    """
    # Verify zone exists
    await _get_polygon_zone_or_404(zone_id, db)

    # Default time window: last 24 hours
    now = utc_now()
    actual_end = end_time or now
    actual_start = start_time or (now - timedelta(hours=24))

    dwell_service = get_dwell_time_service(db)
    distribution = await dwell_service.get_zone_entity_distribution(
        zone_id=zone_id,
        start_time=actual_start,
        end_time=actual_end,
    )

    logger.debug(
        f"Retrieved entity distribution for zone {zone_id}",
        extra={
            "zone_id": zone_id,
            "total_entities": distribution["total_entities"],
            "entity_types_count": len(distribution["entity_types"]),
        },
    )

    return ZoneEntityDistribution(
        zone_id=distribution["zone_id"],
        zone_name=distribution["zone_name"],
        total_entities=distribution["total_entities"],
        entity_types=[EntityTypeCount(**et) for et in distribution["entity_types"]],
    )


@router.get(
    "/entity-distribution",
    response_model=ZoneEntityDistributionResponse,
    summary="Get entity distribution across all polygon zones",
    responses={
        200: {"description": "Entity distribution retrieved successfully"},
    },
)
async def get_all_zones_entity_distribution(
    db: DbSession,
    camera_id: str | None = Query(
        default=None,
        description="Filter by camera ID (optional)",
    ),
    start_time: datetime | None = Query(
        default=None,
        description="Start of time window (defaults to 24 hours ago)",
    ),
    end_time: datetime | None = Query(
        default=None,
        description="End of time window (defaults to now)",
    ),
) -> ZoneEntityDistributionResponse:
    """Get entity type distribution across all polygon zones.

    Returns aggregated entity type counts for all zones, optionally
    filtered by camera.

    Args:
        db: Database session.
        camera_id: Optional camera ID filter.
        start_time: Start of time window (defaults to 24 hours ago).
        end_time: End of time window (defaults to now).

    Returns:
        Entity distribution for all zones with grand total.
    """
    # Default time window: last 24 hours
    now = utc_now()
    actual_end = end_time or now
    actual_start = start_time or (now - timedelta(hours=24))

    # Get all polygon zones, optionally filtered by camera
    polygon_service = get_polygon_zone_service(db)
    if camera_id:
        zones = await polygon_service.get_zones_by_camera(camera_id, active_only=False)
    else:
        # Get all zones across all cameras
        zones = await polygon_service.get_all_zones()

    # Get entity distribution for each zone
    dwell_service = get_dwell_time_service(db)
    zone_distributions = []
    grand_total = 0

    for zone in zones:
        distribution = await dwell_service.get_zone_entity_distribution(
            zone_id=zone.id,
            start_time=actual_start,
            end_time=actual_end,
        )
        zone_distributions.append(
            ZoneEntityDistribution(
                zone_id=distribution["zone_id"],
                zone_name=distribution["zone_name"],
                total_entities=distribution["total_entities"],
                entity_types=[EntityTypeCount(**et) for et in distribution["entity_types"]],
            )
        )
        grand_total += distribution["total_entities"]

    logger.debug(
        f"Retrieved entity distribution for {len(zones)} zones",
        extra={
            "zone_count": len(zones),
            "grand_total": grand_total,
            "camera_id": camera_id,
        },
    )

    return ZoneEntityDistributionResponse(
        zones=zone_distributions,
        grand_total=grand_total,
        start_time=actual_start,
        end_time=actual_end,
    )


# ============================================================================
# Zone Activity Heatmap Endpoints (NEM-5024)
# ============================================================================


@router.get(
    "/polygon-zones/{zone_id}/activity-heatmap",
    response_model=ZoneActivityHeatmapResponse,
    summary="Get activity heatmap data for a polygon zone",
    responses={
        200: {"description": "Activity heatmap retrieved successfully"},
        404: {"description": "Polygon zone not found"},
    },
)
async def get_zone_activity_heatmap(
    zone_id: int,
    db: DbSession,
    time_range: HeatmapTimeRange = Query(
        default=HeatmapTimeRange.DAY_7,
        description="Time range for aggregation: 1h, 6h, 24h, 7d, 30d",
    ),
) -> ZoneActivityHeatmapResponse:
    """Get activity heatmap data for a polygon zone.

    Returns activity patterns aggregated by hour and day of week,
    suitable for rendering a visual heatmap showing when the zone
    is most active.

    The heatmap data includes:
    - Weekly data: Activity counts for each hour/day combination (24 hours x 7 days)
    - Hourly data: Today's activity by hour
    - Total activity count in the time range

    Args:
        zone_id: ID of the polygon zone.
        db: Database session.
        time_range: Time range for aggregation (default: 7 days).

    Returns:
        ZoneActivityHeatmapResponse with heatmap data points.

    Raises:
        HTTPException: 404 if polygon zone not found.
    """
    # Verify zone exists
    await _get_polygon_zone_or_404(zone_id, db)

    # Calculate time window based on time_range
    now = utc_now()
    if time_range == HeatmapTimeRange.HOUR_1:
        start_time = now - timedelta(hours=1)
    elif time_range == HeatmapTimeRange.HOUR_6:
        start_time = now - timedelta(hours=6)
    elif time_range == HeatmapTimeRange.HOUR_24:
        start_time = now - timedelta(hours=24)
    elif time_range == HeatmapTimeRange.DAY_7:
        start_time = now - timedelta(days=7)
    else:  # DAY_30
        start_time = now - timedelta(days=30)

    dwell_service = get_dwell_time_service(db)
    heatmap_data = await dwell_service.get_zone_activity_heatmap(
        zone_id=zone_id,
        start_time=start_time,
        end_time=now,
    )

    logger.debug(
        f"Retrieved activity heatmap for zone {zone_id}",
        extra={
            "zone_id": zone_id,
            "time_range": time_range.value,
            "total_activity": heatmap_data["total_activity"],
        },
    )

    return ZoneActivityHeatmapResponse(
        zone_id=heatmap_data["zone_id"],
        zone_name=heatmap_data["zone_name"],
        time_range=time_range,
        weekly_data=[HeatmapDataPoint(**dp) for dp in heatmap_data["weekly_data"]],
        hourly_data=[HourlyActivity(**ha) for ha in heatmap_data["hourly_data"]],
        total_activity=heatmap_data["total_activity"],
        start_time=start_time,
        end_time=now,
    )


@router.get(
    "/comparison",
    response_model=ZoneComparisonResponse,
    summary="Compare metrics across multiple zones",
    responses={
        200: {"description": "Zone comparison data retrieved successfully"},
        400: {"description": "Invalid metric or period"},
    },
)
async def compare_zones(
    db: DbSession,
    zone_ids: list[int] = Query(..., description="Zone IDs to compare"),
    metric: str = Query(
        default="crossings",
        description="Metric to compare: crossings, dwell_time, anomalies, occupancy",
    ),
    period: str = Query(
        default="day",
        description="Time period: day, week, month",
    ),
) -> ZoneComparisonResponse:
    """Compare specified metric across multiple zones.

    Returns comparison data for the specified zones, including metric values
    and trend percentages where available.

    Args:
        db: Database session.
        zone_ids: List of zone IDs to compare.
        metric: The metric to compare (crossings, dwell_time, anomalies, occupancy).
        period: Time period for comparison (day, week, month).

    Returns:
        ZoneComparisonResponse with comparison data for each zone.

    Raises:
        HTTPException: 400 if metric or period is invalid.
    """
    from backend.services.zone_comparison_service import get_zone_comparison_service

    # Validate metric
    try:
        validated_metric = ComparisonMetric(metric)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid metric '{metric}'. Valid options: crossings, dwell_time, anomalies, occupancy",
        ) from err

    # Validate period
    try:
        validated_period = ComparisonPeriod(period)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid period '{period}'. Valid options: day, week, month",
        ) from err

    # Calculate time window based on period
    now = utc_now()
    if validated_period == ComparisonPeriod.WEEK:
        start_time = now - timedelta(days=7)
    elif validated_period == ComparisonPeriod.MONTH:
        start_time = now - timedelta(days=30)
    else:  # day
        start_time = now - timedelta(days=1)

    service = get_zone_comparison_service(db)
    zones_data = await service.compare_zones(
        zone_ids=zone_ids,
        metric=metric,
        start_time=start_time,
        end_time=now,
    )

    logger.debug(
        f"Retrieved comparison data for {len(zones_data)} zones",
        extra={
            "zone_ids": zone_ids,
            "metric": metric,
            "period": period,
            "results_count": len(zones_data),
        },
    )

    return ZoneComparisonResponse(
        metric=validated_metric,
        zones=[ZoneComparisonData(**z) for z in zones_data],
        start_time=start_time,
        end_time=now,
        comparison_period=validated_period,
    )


# ============================================================================
# Approach Vector Endpoints (NEM-4936)
# ============================================================================


@router.get(
    "/polygon-zones/{zone_id}/approach-vectors",
    response_model=ZoneApproachVectorsResponse,
    summary="Get approach vectors for a polygon zone",
    responses={
        200: {"description": "Approach vectors retrieved successfully"},
        404: {"description": "Polygon zone not found"},
    },
)
async def get_zone_approach_vectors(
    zone_id: int,
    db: DbSession,
) -> ZoneApproachVectorsResponse:
    """Get approach vector analysis for entities approaching a polygon zone.

    Returns real-time movement analysis including direction, speed, and ETA
    for all tracked entities outside the zone that are moving toward it.

    Urgency levels:
    - imminent: ETA < 3 seconds (high priority)
    - approaching: ETA 3-10 seconds (medium priority)
    - distant: ETA > 10 seconds (low priority)
    - not_approaching: Moving away or stationary

    Args:
        zone_id: ID of the polygon zone.
        db: Database session.

    Returns:
        Approach vectors with urgency classification for all approaching entities.

    Raises:
        HTTPException: 404 if polygon zone not found.
    """
    from backend.services.approach_vector_service import get_approach_vector_service

    # Verify zone exists
    await _get_polygon_zone_or_404(zone_id, db)

    # Get polygon zone details
    polygon_service = get_polygon_zone_service(db)
    zone = await polygon_service.get_zone(zone_id)

    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Polygon zone with id {zone_id} not found",
        )

    # Get approach vectors using the new service
    service = get_approach_vector_service(db)
    vectors = await service.get_zone_approach_vectors(zone_id)

    now = utc_now()

    # Convert service results to response schema
    approach_vectors = []
    imminent_count = 0

    for v in vectors:
        urgency = _calculate_urgency(v.get("estimated_arrival_seconds"))
        if urgency == ApproachUrgency.IMMINENT:
            imminent_count += 1

        approach_vectors.append(
            ApproachVectorData(
                track_id=v["track_id"],
                object_class=v["object_class"],
                is_approaching=v["is_approaching"],
                direction_degrees=v["direction_degrees"],
                speed_normalized=v["speed_normalized"],
                distance_to_zone=v["distance_to_zone"],
                estimated_arrival_seconds=v.get("estimated_arrival_seconds"),
                urgency=urgency,
                current_position=v["current_position"],
                zone_centroid=v["zone_centroid"],
            )
        )

    total_approaching = sum(1 for v in approach_vectors if v.is_approaching)

    logger.debug(
        f"Retrieved {len(approach_vectors)} approach vectors for zone {zone_id}",
        extra={
            "zone_id": zone_id,
            "total_approaching": total_approaching,
            "imminent_count": imminent_count,
        },
    )

    return ZoneApproachVectorsResponse(
        zone_id=zone_id,
        zone_name=zone.name,
        approach_vectors=approach_vectors,
        total_approaching=total_approaching,
        imminent_count=imminent_count,
        timestamp=now,
    )


@router.get(
    "/approach-vectors/camera/{camera_id}",
    response_model=CameraApproachVectorsResponse,
    summary="Get approach vectors for all zones on a camera",
    responses={
        200: {"description": "Approach vectors retrieved successfully"},
        404: {"description": "Camera not found"},
    },
)
async def get_camera_approach_vectors(
    camera_id: str,
    db: DbSession,
) -> CameraApproachVectorsResponse:
    """Get approach vectors for all polygon zones on a camera.

    Aggregates approach vector data across all zones for efficient
    visualization of approaching entities on the camera view.

    Args:
        camera_id: ID of the camera.
        db: Database session.

    Returns:
        Approach vectors for all zones on the camera.

    Raises:
        HTTPException: 404 if camera not found.
    """
    from backend.services.approach_vector_service import get_approach_vector_service

    # Verify camera exists
    await get_camera_or_404(camera_id, db)

    # Get all polygon zones for this camera
    polygon_service = get_polygon_zone_service(db)
    zones = await polygon_service.get_zones_by_camera(camera_id, active_only=True)

    service = get_approach_vector_service(db)
    now = utc_now()

    zone_responses = []
    total_approaching_entities = 0

    for zone in zones:
        vectors = await service.get_zone_approach_vectors(zone.id)

        approach_vectors = []
        imminent_count = 0

        for v in vectors:
            urgency = _calculate_urgency(v.get("estimated_arrival_seconds"))
            if urgency == ApproachUrgency.IMMINENT:
                imminent_count += 1

            approach_vectors.append(
                ApproachVectorData(
                    track_id=v["track_id"],
                    object_class=v["object_class"],
                    is_approaching=v["is_approaching"],
                    direction_degrees=v["direction_degrees"],
                    speed_normalized=v["speed_normalized"],
                    distance_to_zone=v["distance_to_zone"],
                    estimated_arrival_seconds=v.get("estimated_arrival_seconds"),
                    urgency=urgency,
                    current_position=v["current_position"],
                    zone_centroid=v["zone_centroid"],
                )
            )

        total_approaching = sum(1 for v in approach_vectors if v.is_approaching)
        total_approaching_entities += total_approaching

        zone_responses.append(
            ZoneApproachVectorsResponse(
                zone_id=zone.id,
                zone_name=zone.name,
                approach_vectors=approach_vectors,
                total_approaching=total_approaching,
                imminent_count=imminent_count,
                timestamp=now,
            )
        )

    logger.debug(
        f"Retrieved approach vectors for {len(zones)} zones on camera {camera_id}",
        extra={
            "camera_id": camera_id,
            "zone_count": len(zones),
            "total_approaching": total_approaching_entities,
        },
    )

    return CameraApproachVectorsResponse(
        camera_id=camera_id,
        zones=zone_responses,
        total_zones=len(zones),
        total_approaching_entities=total_approaching_entities,
    )


def _calculate_urgency(estimated_arrival_seconds: float | None) -> ApproachUrgency:
    """Calculate urgency level based on ETA.

    Args:
        estimated_arrival_seconds: ETA to zone in seconds, or None if not approaching.

    Returns:
        Urgency level (imminent, approaching, distant, or not_approaching).
    """
    if estimated_arrival_seconds is None:
        return ApproachUrgency.NOT_APPROACHING

    if estimated_arrival_seconds < 3.0:
        return ApproachUrgency.IMMINENT
    elif estimated_arrival_seconds < 10.0:
        return ApproachUrgency.APPROACHING
    else:
        return ApproachUrgency.DISTANT
