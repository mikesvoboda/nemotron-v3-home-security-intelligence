"""API routes for object track trajectory management.

This module provides endpoints for retrieving track history, trajectory points,
and lists of tracks for multi-object tracking (MOT) functionality.

Tracks represent the movement path of detected objects across video frames,
enabling motion analysis, trajectory prediction, and behavioral analysis.
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import ORJSONResponse

from backend.api.dependencies import DbSession
from backend.api.schemas.track import (
    TrackHistoryResponse,
    TrackListResponse,
    TrajectoryPoint,
)
from backend.core.logging import get_logger
from backend.services.track_service import get_track_service

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/tracks",
    tags=["tracks"],
    default_response_class=ORJSONResponse,
)


@router.get("/{camera_id}/{track_id}", response_model=TrackHistoryResponse)
async def get_track_history(
    camera_id: str,
    track_id: int,
    db: DbSession,
) -> TrackHistoryResponse:
    """Get full track history with trajectory and metrics.

    Returns the complete trajectory data and computed movement metrics
    for a specific track, suitable for visualization and analysis.

    Args:
        camera_id: ID of the camera where the track was observed.
        track_id: Tracker-assigned track ID (unique per camera session).
        db: Database session.

    Returns:
        TrackHistoryResponse with full trajectory and movement metrics.

    Raises:
        HTTPException: 404 if track not found.

    Example:
        GET /api/tracks/front_door/42
        Returns trajectory points and metrics for track 42 on front_door camera.
    """
    service = get_track_service(db)
    history = await service.get_track_history(track_id=track_id, camera_id=camera_id)

    if history is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Track {track_id} not found for camera {camera_id}",
        )

    return history


@router.get("/{camera_id}/{track_id}/trajectory", response_model=list[TrajectoryPoint])
async def get_track_trajectory(
    camera_id: str,
    track_id: int,
    db: DbSession,
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of trajectory points"),
) -> list[TrajectoryPoint]:
    """Get just the trajectory points for a track.

    Returns only the position data (x, y, timestamp) for efficient
    trajectory plotting without full track metadata.

    Args:
        camera_id: ID of the camera where the track was observed.
        track_id: Tracker-assigned track ID (unique per camera session).
        db: Database session.
        limit: Maximum number of trajectory points to return (default 100, max 1000).
            Returns the most recent points if trajectory exceeds limit.

    Returns:
        List of TrajectoryPoint objects ordered by timestamp.

    Raises:
        HTTPException: 404 if track not found.

    Example:
        GET /api/tracks/front_door/42/trajectory?limit=50
        Returns up to 50 most recent trajectory points.
    """
    service = get_track_service(db)
    history = await service.get_track_history(track_id=track_id, camera_id=camera_id)

    if history is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Track {track_id} not found for camera {camera_id}",
        )

    # Return limited trajectory points (most recent if exceeds limit)
    trajectory = history.trajectory
    if len(trajectory) > limit:
        trajectory = trajectory[-limit:]

    return trajectory


@router.get("/camera/{camera_id}", response_model=TrackListResponse)
async def get_tracks_by_camera(
    camera_id: str,
    db: DbSession,
    start_time: datetime | None = Query(
        None, description="Filter tracks starting after this time (ISO format)"
    ),
    end_time: datetime | None = Query(
        None, description="Filter tracks starting before this time (ISO format)"
    ),
    object_class: str | None = Query(
        None, description="Filter by object class (e.g., 'person', 'car')"
    ),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Number of items per page"),
) -> TrackListResponse:
    """Get paginated list of tracks for a camera.

    Returns a list of tracks observed on a specific camera with optional
    filtering by time range and object class. Results are ordered by
    first_seen timestamp (newest first).

    Args:
        camera_id: ID of the camera to query tracks for.
        db: Database session.
        start_time: Optional start time filter (inclusive, ISO format).
        end_time: Optional end time filter (inclusive, ISO format).
        object_class: Optional filter by object class (e.g., 'person', 'car').
        page: Page number (1-indexed, default 1).
        page_size: Number of items per page (1-100, default 50).

    Returns:
        TrackListResponse with paginated tracks and total count.

    Example:
        GET /api/tracks/camera/front_door?object_class=person&page=1&page_size=25
        Returns first 25 person tracks from front_door camera.
    """
    service = get_track_service(db)
    result = await service.get_tracks_by_camera(
        camera_id=camera_id,
        start_time=start_time,
        end_time=end_time,
        object_class=object_class,
        page=page,
        page_size=page_size,
    )

    return result
