"""API routes for analytics zones (line zones and polygon zones).

This module provides CRUD endpoints for managing analytics zones:
- Line zones: Virtual tripwires for counting and detecting line crossings
- Polygon zones: Region-based intrusion detection and object counting
- Dwell time tracking: Monitor how long objects stay in polygon zones

Analytics zones are camera-specific and can be configured per camera to define
areas of interest for automated analytics.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import ORJSONResponse

from backend.api.dependencies import DbSession, get_camera_or_404
from backend.api.schemas.analytics_zone import (
    LineZoneCreate,
    LineZoneListResponse,
    LineZoneResponse,
    LineZoneUpdate,
    PolygonZoneCreate,
    PolygonZoneListResponse,
    PolygonZoneResponse,
    PolygonZoneUpdate,
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
