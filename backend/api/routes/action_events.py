"""API routes for action event management.

This module provides endpoints for X-CLIP action recognition results,
including listing, filtering, and triggering action analysis on video frames.

Endpoints:
    GET    /api/action-events                      - List all action events
    GET    /api/action-events/suspicious           - List suspicious actions only
    GET    /api/action-events/{event_id}           - Get single action event
    GET    /api/action-events/camera/{camera_id}   - Get events for a camera
    POST   /api/action-events/analyze              - Trigger action analysis on frames

Linear issue: NEM-3714
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.action_event import (
    ActionAnalyzeRequest,
    ActionAnalyzeResponse,
    ActionEventCreate,
    ActionEventListResponse,
    ActionEventResponse,
    SuspiciousActionsResponse,
)
from backend.api.schemas.pagination import PaginationMeta
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.models.action_event import ActionEvent
from backend.services.action_recognition_service import ActionRecognitionService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/action-events", tags=["action-events"])


def _action_event_to_response(event: ActionEvent) -> ActionEventResponse:
    """Convert ActionEvent model to response schema."""
    return ActionEventResponse(
        id=event.id,
        camera_id=event.camera_id,
        track_id=event.track_id,
        action=event.action,
        confidence=event.confidence,
        is_suspicious=event.is_suspicious,
        timestamp=event.timestamp,
        frame_count=event.frame_count,
        all_scores=event.all_scores,
        created_at=event.created_at,
    )


@router.get(
    "",
    response_model=ActionEventListResponse,
    responses={
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def list_action_events(
    camera_id: str | None = Query(None, description="Filter by camera ID"),
    track_id: int | None = Query(None, description="Filter by track ID"),
    action: str | None = Query(None, description="Filter by action label"),
    is_suspicious: bool | None = Query(None, description="Filter by suspicious flag"),
    min_confidence: float | None = Query(
        None, ge=0.0, le=1.0, description="Filter by minimum confidence"
    ),
    start_time: datetime | None = Query(None, description="Filter by start time"),
    end_time: datetime | None = Query(None, description="Filter by end time"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: AsyncSession = Depends(get_db),
) -> ActionEventListResponse:
    """List action events with optional filtering and pagination.

    Args:
        camera_id: Filter by camera ID
        track_id: Filter by track ID
        action: Filter by action label (exact match)
        is_suspicious: Filter by suspicious flag
        min_confidence: Filter by minimum confidence score
        start_time: Filter by timestamp >= start_time
        end_time: Filter by timestamp <= end_time
        limit: Maximum number of results to return
        offset: Number of results to skip for pagination
        db: Database session

    Returns:
        ActionEventListResponse with events and pagination info
    """
    service = ActionRecognitionService(session=db)

    events, total = await service.get_action_events(
        camera_id=camera_id,
        track_id=track_id,
        action=action,
        is_suspicious=is_suspicious,
        min_confidence=min_confidence,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )

    return ActionEventListResponse(
        items=[_action_event_to_response(e) for e in events],
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            has_more=total > offset + limit,
        ),
    )


@router.get(
    "/suspicious",
    response_model=SuspiciousActionsResponse,
    responses={
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def list_suspicious_actions(
    camera_id: str | None = Query(None, description="Filter by camera ID"),
    min_confidence: float | None = Query(
        None, ge=0.0, le=1.0, description="Filter by minimum confidence"
    ),
    start_time: datetime | None = Query(None, description="Filter by start time"),
    end_time: datetime | None = Query(None, description="Filter by end time"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: AsyncSession = Depends(get_db),
) -> SuspiciousActionsResponse:
    """List suspicious action events only.

    Returns action events where is_suspicious=True, along with
    counts of suspicious vs total events.

    Args:
        camera_id: Filter by camera ID
        min_confidence: Filter by minimum confidence score
        start_time: Filter by timestamp >= start_time
        end_time: Filter by timestamp <= end_time
        limit: Maximum number of results to return
        offset: Number of results to skip for pagination
        db: Database session

    Returns:
        SuspiciousActionsResponse with suspicious events and counts
    """
    service = ActionRecognitionService(session=db)

    events, suspicious_count, total_count = await service.get_suspicious_actions(
        camera_id=camera_id,
        min_confidence=min_confidence,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )

    return SuspiciousActionsResponse(
        items=[_action_event_to_response(e) for e in events],
        pagination=PaginationMeta(
            total=suspicious_count,
            limit=limit,
            offset=offset,
            has_more=suspicious_count > offset + limit,
        ),
        suspicious_count=suspicious_count,
        total_count=total_count,
    )


@router.get(
    "/{event_id}",
    response_model=ActionEventResponse,
    responses={
        404: {"description": "Action event not found"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def get_action_event(
    event_id: int = Path(..., ge=1, description="Action event ID"),
    db: AsyncSession = Depends(get_db),
) -> ActionEventResponse:
    """Get a specific action event by ID.

    Args:
        event_id: Action event ID
        db: Database session

    Returns:
        ActionEventResponse

    Raises:
        HTTPException: 404 if event not found
    """
    service = ActionRecognitionService(session=db)

    event = await service.get_action_event(event_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action event {event_id} not found",
        )

    return _action_event_to_response(event)


@router.get(
    "/camera/{camera_id}",
    response_model=ActionEventListResponse,
    responses={
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def get_camera_action_events(
    camera_id: str = Path(..., description="Camera ID"),
    start_time: datetime | None = Query(None, description="Filter by start time"),
    end_time: datetime | None = Query(None, description="Filter by end time"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: AsyncSession = Depends(get_db),
) -> ActionEventListResponse:
    """Get action events for a specific camera.

    Convenience endpoint for camera-specific queries.

    Args:
        camera_id: Camera ID to filter by
        start_time: Filter by timestamp >= start_time
        end_time: Filter by timestamp <= end_time
        limit: Maximum number of results to return
        offset: Number of results to skip for pagination
        db: Database session

    Returns:
        ActionEventListResponse with events and pagination info
    """
    service = ActionRecognitionService(session=db)

    events, total = await service.get_action_events_for_camera(
        camera_id=camera_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )

    return ActionEventListResponse(
        items=[_action_event_to_response(e) for e in events],
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            has_more=total > offset + limit,
        ),
    )


@router.post(
    "/analyze",
    response_model=ActionAnalyzeResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Invalid request (no valid frames)"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
        503: {"description": "X-CLIP model unavailable"},
    },
)
async def analyze_action(
    request: ActionAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
) -> ActionAnalyzeResponse:
    """Trigger action analysis on a set of video frames.

    This endpoint loads frames from disk, runs X-CLIP classification,
    and optionally saves the result to the database.

    The X-CLIP model analyzes frame sequences to detect security-relevant
    actions like walking, running, climbing, loitering, etc.

    Args:
        request: Analysis request with frame paths and options
        db: Database session

    Returns:
        ActionAnalyzeResponse with detected action and scores

    Raises:
        HTTPException: 400 if no valid frames, 503 if model unavailable
    """
    service = ActionRecognitionService(session=db)

    try:
        result = await service.analyze_frames(
            camera_id=request.camera_id,
            frame_paths=request.frame_paths,
            track_id=request.track_id,
            confidence_threshold=request.confidence_threshold,
            save_event=request.save_event,
        )

        # Commit if we saved an event
        if result.get("saved"):
            await db.commit()

        return ActionAnalyzeResponse(
            action=result["action"],
            confidence=result["confidence"],
            is_suspicious=result["is_suspicious"],
            all_scores=result["all_scores"],
            frame_count=result["frame_count"],
            event_id=result.get("event_id"),
            saved=result.get("saved", False),
        )

    except ValueError as e:
        # Invalid frames or empty input
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    except RuntimeError as e:
        # Model loading or classification failure
        logger.error(f"Action analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"X-CLIP model unavailable: {e}",
        ) from e


@router.post(
    "",
    response_model=ActionEventResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def create_action_event(
    event_data: ActionEventCreate,
    db: AsyncSession = Depends(get_db),
) -> ActionEventResponse:
    """Create a new action event manually.

    This endpoint allows creating action events without running analysis,
    useful for importing results from external systems or testing.

    Args:
        event_data: Action event data
        db: Database session

    Returns:
        Created ActionEventResponse
    """
    service = ActionRecognitionService(session=db)

    event = await service.create_action_event(
        camera_id=event_data.camera_id,
        track_id=event_data.track_id,
        action=event_data.action,
        confidence=event_data.confidence,
        is_suspicious=event_data.is_suspicious,
        timestamp=event_data.timestamp,
        frame_count=event_data.frame_count,
        all_scores=event_data.all_scores,
    )

    await db.commit()
    await db.refresh(event)

    return _action_event_to_response(event)


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"description": "Action event not found"},
        500: {"description": "Internal server error"},
    },
)
async def delete_action_event(
    event_id: int = Path(..., ge=1, description="Action event ID"),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an action event.

    Args:
        event_id: Action event ID to delete
        db: Database session

    Raises:
        HTTPException: 404 if event not found
    """
    service = ActionRecognitionService(session=db)

    deleted = await service.delete_action_event(event_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action event {event_id} not found",
        )

    await db.commit()
