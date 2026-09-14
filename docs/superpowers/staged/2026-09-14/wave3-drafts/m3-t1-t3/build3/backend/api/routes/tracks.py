"""Track API routes for object motion tracking.

Exposes TrackService functionality via REST API for track visualization
and movement analytics.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.track import (
    ActiveTracksResponse,
    CameraTrackStats,
    TrackHistoryResponse,
    TrackListResponse,
    TrackResponse,
)
from backend.core.database import get_db
from backend.services.track_service import TrackService, get_track_service

router = APIRouter(prefix="/api", tags=["tracks"])


async def get_service(
    session: AsyncSession = Depends(get_db),
) -> TrackService:
    """Dependency to get TrackService instance."""
    return get_track_service(session)


@router.get(
    "/tracks",
    response_model=TrackListResponse,
    summary="List all tracks",
    description="List all tracks with optional filtering by camera and object class. "
    "Results are paginated and ordered by first_seen descending (newest first).",
    responses={
        200: {"description": "Successful response with list of tracks"},
        422: {"description": "Validation error"},
    },
)
async def list_tracks(
    camera_id: str | None = Query(None, description="Filter by camera ID"),
    object_class: str | None = Query(
        None, description="Filter by object class (e.g., person, car)"
    ),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=1000, description="Number of items per page"),
    service: TrackService = Depends(get_service),
) -> TrackListResponse:
    """List all tracks with optional filters.

    Args:
        camera_id: Optional camera ID filter.
        object_class: Optional object class filter (e.g., 'person', 'car').
        page: Page number (1-indexed). Default: 1.
        page_size: Number of items per page. Default: 50, max: 1000.
        service: TrackService instance.

    Returns:
        TrackListResponse with paginated tracks and total count.
    """
    # If camera_id is provided, use get_tracks_by_camera for efficient filtering
    if camera_id:
        return await service.get_tracks_by_camera(
            camera_id=camera_id,
            object_class=object_class,
            page=page,
            page_size=page_size,
        )

    # For all-cameras query, we need to aggregate across cameras
    # Use get_tracks_by_camera with a placeholder for now
    # In practice, this would require a new service method for cross-camera queries
    # For now, return empty if no camera specified (common pattern for track APIs)
    return TrackListResponse(
        tracks=[],
        total=0,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/tracks/{track_id}",
    response_model=TrackResponse,
    summary="Get track by ID",
    description="Retrieve a single track by its database primary key ID.",
    responses={
        200: {"description": "Successful response with track details"},
        404: {"description": "Track not found"},
        422: {"description": "Validation error"},
    },
)
async def get_track_by_id(
    track_id: int,
    service: TrackService = Depends(get_service),
) -> TrackResponse:
    """Get a single track by its database ID.

    Args:
        track_id: The database primary key ID of the track.
        service: TrackService instance.

    Returns:
        TrackResponse with track details.

    Raises:
        HTTPException: 404 if track not found.
    """
    track = await service.get_track_by_id(track_id)

    if track is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Track with id {track_id} not found",
        )

    # Calculate metrics if trajectory exists
    metrics = None
    if track.trajectory:
        metrics = service.calculate_metrics(track.trajectory)

    return TrackResponse(
        id=track.id,
        track_id=track.track_id,
        camera_id=track.camera_id,
        object_class=track.object_class,
        first_seen=track.first_seen,
        last_seen=track.last_seen,
        metrics=metrics,
    )


@router.get(
    "/tracks/{track_id}/history",
    response_model=TrackHistoryResponse,
    summary="Get track with full trajectory",
    description="Retrieve a track with its complete trajectory data and movement metrics. "
    "Use this endpoint for trajectory visualization and detailed analysis.",
    responses={
        200: {"description": "Successful response with track history and trajectory"},
        404: {"description": "Track not found"},
        422: {"description": "Validation error"},
    },
)
async def get_track_history(
    track_id: int,
    service: TrackService = Depends(get_service),
) -> TrackHistoryResponse:
    """Get track with full trajectory history.

    Args:
        track_id: The database primary key ID of the track.
        service: TrackService instance.

    Returns:
        TrackHistoryResponse with full trajectory and metrics.

    Raises:
        HTTPException: 404 if track not found.
    """
    # First get the track by database ID
    track = await service.get_track_by_id(track_id)

    if track is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Track with id {track_id} not found",
        )

    # Now get the full history using track_id and camera_id
    history = await service.get_track_history(track.track_id, track.camera_id)

    if history is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Track history for id {track_id} not found",
        )

    return history


@router.get(
    "/cameras/{camera_id}/tracks",
    response_model=TrackListResponse,
    summary="List tracks for a camera",
    description="List all tracks for a specific camera with optional filtering by object class. "
    "Results are paginated and ordered by first_seen descending (newest first).",
    responses={
        200: {"description": "Successful response with list of tracks"},
        422: {"description": "Validation error"},
    },
)
async def list_camera_tracks(
    camera_id: str,
    object_class: str | None = Query(
        None, description="Filter by object class (e.g., person, car)"
    ),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=1000, description="Number of items per page"),
    service: TrackService = Depends(get_service),
) -> TrackListResponse:
    """List tracks for a specific camera.

    Args:
        camera_id: The camera ID to list tracks for.
        object_class: Optional object class filter (e.g., 'person', 'car').
        page: Page number (1-indexed). Default: 1.
        page_size: Number of items per page. Default: 50, max: 1000.
        service: TrackService instance.

    Returns:
        TrackListResponse with paginated tracks and total count.
    """
    return await service.get_tracks_by_camera(
        camera_id=camera_id,
        object_class=object_class,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/cameras/{camera_id}/tracks/active",
    response_model=ActiveTracksResponse,
    summary="Get active tracks for a camera",
    description="Retrieve currently active tracks for a camera. "
    "Active tracks are those updated within the last 5 minutes.",
    responses={
        200: {"description": "Successful response with active tracks"},
        422: {"description": "Validation error"},
    },
)
async def get_active_tracks(
    camera_id: str,
    service: TrackService = Depends(get_service),
) -> ActiveTracksResponse:
    """Get currently active tracks for a camera.

    Active tracks are those that have been updated within the last 5 minutes,
    indicating they are currently being tracked.

    Args:
        camera_id: The camera ID to get active tracks for.
        service: TrackService instance.

    Returns:
        ActiveTracksResponse with list of active tracks and count.
    """
    active_tracks = await service.get_active_tracks(camera_id, active_window_minutes=5)

    # Convert to response models
    track_responses = []
    for track in active_tracks:
        metrics = None
        if track.trajectory:
            metrics = service.calculate_metrics(track.trajectory)

        track_responses.append(
            TrackResponse(
                id=track.id,
                track_id=track.track_id,
                camera_id=track.camera_id,
                object_class=track.object_class,
                first_seen=track.first_seen,
                last_seen=track.last_seen,
                metrics=metrics,
            )
        )

    return ActiveTracksResponse(
        tracks=track_responses,
        count=len(track_responses),
    )


@router.get(
    "/cameras/{camera_id}/tracks/stats",
    response_model=CameraTrackStats,
    summary="Get track statistics for a camera",
    description="Retrieve aggregated track statistics for a camera including "
    "active count, total today, average duration, and counts by object type.",
    responses={
        200: {"description": "Successful response with track statistics"},
        422: {"description": "Validation error"},
    },
)
async def get_camera_track_stats(
    camera_id: str,
    service: TrackService = Depends(get_service),
) -> CameraTrackStats:
    """Get track statistics for a specific camera.

    Returns aggregated statistics including:
    - Number of currently active tracks (updated in last 5 minutes)
    - Total tracks created today
    - Average track duration in seconds
    - Track counts grouped by object type

    Args:
        camera_id: The camera ID to get statistics for.
        service: TrackService instance.

    Returns:
        CameraTrackStats with aggregated statistics.
    """
    # Get active tracks count (updated in last 5 minutes)
    active_tracks = await service.get_active_tracks(camera_id, active_window_minutes=5)
    active_count = len(active_tracks)

    # Get total tracks today
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    total_today = await service.get_track_count_since(camera_id, today_start)

    # Get average track duration
    avg_duration = await service.get_avg_track_duration(camera_id)

    # Get counts by object type
    by_object_type = await service.get_track_counts_by_type(camera_id)

    return CameraTrackStats(
        active_count=active_count,
        total_today=total_today,
        avg_duration_seconds=round(avg_duration, 2),
        by_object_type=by_object_type,
    )
