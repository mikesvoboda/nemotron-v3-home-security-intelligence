"""API routes for heatmap visualization endpoints.

This module provides REST API endpoints for retrieving and managing
movement heatmap data for cameras.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.heatmap import (
    HeatmapListResponse,
    HeatmapMetadata,
    HeatmapResolution,
    HeatmapResponse,
    HeatmapSnapshotRequest,
    HeatmapSnapshotResponse,
)
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.models.camera import Camera
from backend.models.heatmap import HeatmapResolution as ModelHeatmapResolution
from backend.services.heatmap_service import get_heatmap_service

logger = get_logger(__name__)
router = APIRouter(prefix="/api/heatmaps", tags=["heatmaps"])


async def _verify_camera_exists(camera_id: str, db: AsyncSession) -> Camera:
    """Verify that a camera exists and return it.

    Args:
        camera_id: ID of the camera to verify.
        db: Database session.

    Returns:
        Camera model instance.

    Raises:
        HTTPException: 404 if camera not found.
    """
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()

    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera not found: {camera_id}",
        )

    return camera


@router.get(
    "/camera/{camera_id}",
    response_model=HeatmapResponse,
    responses={
        404: {"description": "Camera not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_current_heatmap(
    camera_id: str = Path(..., description="Camera ID"),
    resolution: HeatmapResolution = Query(
        HeatmapResolution.HOURLY,
        description="Heatmap resolution",
    ),
    output_width: int = Query(640, description="Output image width", ge=100, le=4096),
    output_height: int = Query(480, description="Output image height", ge=100, le=4096),
    colormap: str = Query("jet", description="Colormap name (e.g., jet, hot, viridis)"),
    db: AsyncSession = Depends(get_db),
) -> HeatmapResponse:
    """Get the current heatmap image for a camera.

    Returns a heatmap visualization based on the current in-memory accumulator
    for the specified camera. If no accumulator exists, returns an empty heatmap.

    Args:
        camera_id: ID of the camera.
        resolution: Requested resolution (for metadata).
        output_width: Width of the output image in pixels.
        output_height: Height of the output image in pixels.
        colormap: Matplotlib colormap name.
        db: Database session.

    Returns:
        HeatmapResponse with base64-encoded image and metadata.

    Raises:
        HTTPException: 404 if camera not found.
    """
    # Verify camera exists
    await _verify_camera_exists(camera_id, db)

    # Get heatmap service
    service = get_heatmap_service()

    # Generate heatmap image
    heatmap_data = service.get_heatmap_image(
        camera_id,
        output_width=output_width,
        output_height=output_height,
        colormap=colormap,
    )

    # Calculate current time bucket
    now = datetime.now(UTC)
    if resolution == HeatmapResolution.HOURLY:
        time_bucket = now.replace(minute=0, second=0, microsecond=0)
    elif resolution == HeatmapResolution.DAILY:
        time_bucket = now.replace(hour=0, minute=0, second=0, microsecond=0)
    else:  # WEEKLY
        days_since_monday = now.weekday()
        week_start = now - timedelta(days=days_since_monday)
        time_bucket = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

    return HeatmapResponse(
        camera_id=camera_id,
        resolution=resolution,
        time_bucket=time_bucket,
        image_base64=heatmap_data["image_base64"],
        width=heatmap_data["width"],
        height=heatmap_data["height"],
        total_detections=heatmap_data["total_detections"],
        colormap=heatmap_data["colormap"],
    )


@router.get(
    "/camera/{camera_id}/history",
    response_model=HeatmapListResponse,
    responses={
        400: {"description": "Bad request - Invalid date range"},
        404: {"description": "Camera not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_heatmap_history(
    camera_id: str = Path(..., description="Camera ID"),
    start_time: datetime = Query(..., description="Start of the time range (ISO format)"),
    end_time: datetime = Query(..., description="End of the time range (ISO format)"),
    resolution: HeatmapResolution | None = Query(None, description="Filter by resolution level"),
    limit: int = Query(50, description="Maximum number of records to return", ge=1, le=1000),
    offset: int = Query(0, description="Number of records to skip", ge=0),
    db: AsyncSession = Depends(get_db),
) -> HeatmapListResponse:
    """Get historical heatmap metadata for a camera.

    Returns a list of heatmap metadata records for the specified time range.
    Does not include the full heatmap images - use the individual heatmap
    endpoint to retrieve specific images.

    Args:
        camera_id: ID of the camera.
        start_time: Start of the time range.
        end_time: End of the time range.
        resolution: Optional filter by resolution level.
        limit: Maximum number of records to return.
        offset: Number of records to skip.
        db: Database session.

    Returns:
        HeatmapListResponse with metadata records and total count.

    Raises:
        HTTPException: 400 if start_time is after end_time.
        HTTPException: 404 if camera not found.
    """
    # Validate date range
    if start_time > end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_time must be before or equal to end_time",
        )

    # Verify camera exists
    await _verify_camera_exists(camera_id, db)

    # Get heatmap service
    service = get_heatmap_service()

    # Convert schema resolution to model resolution
    model_resolution = None
    if resolution:
        model_resolution = ModelHeatmapResolution(resolution.value)

    # Query historical data
    heatmaps, total = await service.get_heatmap_data(
        session=db,
        camera_id=camera_id,
        start_time=start_time,
        end_time=end_time,
        resolution=model_resolution,
        limit=limit,
        offset=offset,
    )

    # Convert to response schema
    metadata_list = [
        HeatmapMetadata(
            id=h.id,
            camera_id=h.camera_id,
            time_bucket=h.time_bucket,
            resolution=HeatmapResolution(h.resolution),
            width=h.width,
            height=h.height,
            total_detections=h.total_detections,
            created_at=h.created_at,
            updated_at=h.updated_at,
        )
        for h in heatmaps
    ]

    return HeatmapListResponse(heatmaps=metadata_list, total=total)


@router.get(
    "/camera/{camera_id}/merged",
    response_model=HeatmapResponse,
    responses={
        400: {"description": "Bad request - Invalid date range"},
        404: {"description": "Camera not found or no heatmap data"},
        500: {"description": "Internal server error"},
    },
)
async def get_merged_heatmap(
    camera_id: str = Path(..., description="Camera ID"),
    start_time: datetime = Query(..., description="Start of the time range (ISO format)"),
    end_time: datetime = Query(..., description="End of the time range (ISO format)"),
    resolution: HeatmapResolution | None = Query(None, description="Filter by resolution level"),
    db: AsyncSession = Depends(get_db),
) -> HeatmapResponse:
    """Get a merged heatmap from multiple records in a time range.

    Combines all heatmap data in the specified time range into a single
    visualization, showing activity patterns across the entire period.

    Args:
        camera_id: ID of the camera.
        start_time: Start of the time range.
        end_time: End of the time range.
        resolution: Optional filter by resolution level.
        db: Database session.

    Returns:
        HeatmapResponse with merged heatmap image.

    Raises:
        HTTPException: 400 if start_time is after end_time.
        HTTPException: 404 if camera not found or no data in range.
    """
    # Validate date range
    if start_time > end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_time must be before or equal to end_time",
        )

    # Verify camera exists
    await _verify_camera_exists(camera_id, db)

    # Get heatmap service
    service = get_heatmap_service()

    # Convert schema resolution to model resolution
    model_resolution = None
    if resolution:
        model_resolution = ModelHeatmapResolution(resolution.value)

    # Get merged heatmap
    merged_data = await service.get_merged_heatmap(
        session=db,
        camera_id=camera_id,
        start_time=start_time,
        end_time=end_time,
        resolution=model_resolution,
    )

    if merged_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No heatmap data found for the specified time range",
        )

    return HeatmapResponse(
        camera_id=camera_id,
        resolution=resolution or HeatmapResolution.DAILY,
        time_bucket=start_time,  # Use start_time as reference
        image_base64=merged_data["image_base64"],
        width=merged_data["width"],
        height=merged_data["height"],
        total_detections=merged_data["total_detections"],
        colormap=merged_data["colormap"],
    )


@router.post(
    "/camera/{camera_id}/snapshot",
    response_model=HeatmapSnapshotResponse,
    responses={
        404: {"description": "Camera not found"},
        500: {"description": "Internal server error"},
    },
)
async def save_heatmap_snapshot(
    camera_id: str = Path(..., description="Camera ID"),
    request: HeatmapSnapshotRequest = HeatmapSnapshotRequest(),
    db: AsyncSession = Depends(get_db),
) -> HeatmapSnapshotResponse:
    """Force save the current heatmap accumulator to the database.

    Manually triggers a snapshot of the current in-memory heatmap data
    for the specified camera. Useful for debugging or manual data capture.

    Args:
        camera_id: ID of the camera.
        request: Snapshot request with resolution.
        db: Database session.

    Returns:
        HeatmapSnapshotResponse with save status.

    Raises:
        HTTPException: 404 if camera not found.
    """
    # Verify camera exists
    await _verify_camera_exists(camera_id, db)

    # Get heatmap service
    service = get_heatmap_service()

    # Convert schema resolution to model resolution
    model_resolution = ModelHeatmapResolution(request.resolution.value)

    # Save snapshot
    heatmap = await service.save_snapshot(
        session=db,
        camera_id=camera_id,
        resolution=model_resolution,
    )

    if heatmap is None:
        return HeatmapSnapshotResponse(
            success=False,
            message="No heatmap data to save - accumulator is empty",
            heatmap_id=None,
            total_detections=0,
        )

    logger.info(
        f"Saved heatmap snapshot for camera {camera_id}",
        extra={
            "camera_id": camera_id,
            "heatmap_id": heatmap.id,
            "resolution": model_resolution.value,
            "total_detections": heatmap.total_detections,
        },
    )

    return HeatmapSnapshotResponse(
        success=True,
        message="Heatmap snapshot saved successfully",
        heatmap_id=heatmap.id,
        total_detections=heatmap.total_detections,
    )


@router.get(
    "/camera/{camera_id}/stats",
    responses={
        404: {"description": "Camera not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_heatmap_stats(
    camera_id: str = Path(..., description="Camera ID"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get statistics about the current heatmap accumulator for a camera.

    Returns information about the in-memory accumulator including total
    detections, dimensions, and intensity statistics.

    Args:
        camera_id: ID of the camera.
        db: Database session.

    Returns:
        Dictionary with accumulator statistics.

    Raises:
        HTTPException: 404 if camera not found.
    """
    # Verify camera exists
    await _verify_camera_exists(camera_id, db)

    # Get heatmap service
    service = get_heatmap_service()

    # Get accumulator stats
    stats = service.get_accumulator_stats(camera_id)

    if stats is None:
        return {
            "camera_id": camera_id,
            "total_detections": 0,
            "grid_width": service.grid_width,
            "grid_height": service.grid_height,
            "message": "No accumulator exists for this camera",
        }

    return stats


@router.delete(
    "/camera/{camera_id}/accumulator",
    responses={
        404: {"description": "Camera not found"},
        500: {"description": "Internal server error"},
    },
)
async def reset_heatmap_accumulator(
    camera_id: str = Path(..., description="Camera ID"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Reset the heatmap accumulator for a camera.

    Clears all accumulated detection data from memory. This does not
    affect saved heatmap records in the database.

    Args:
        camera_id: ID of the camera.
        db: Database session.

    Returns:
        Dictionary with reset status.

    Raises:
        HTTPException: 404 if camera not found.
    """
    # Verify camera exists
    await _verify_camera_exists(camera_id, db)

    # Get heatmap service
    service = get_heatmap_service()

    # Reset accumulator
    was_reset = service.reset_accumulator(camera_id)

    if was_reset:
        logger.info(
            f"Reset heatmap accumulator for camera {camera_id}",
            extra={"camera_id": camera_id},
        )
        return {
            "camera_id": camera_id,
            "reset": True,
            "message": "Heatmap accumulator reset successfully",
        }
    else:
        return {
            "camera_id": camera_id,
            "reset": False,
            "message": "No accumulator existed for this camera",
        }
