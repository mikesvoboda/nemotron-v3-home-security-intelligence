"""API routes for action event management.

This module provides endpoints for action recognition results stored in the
action_events table, including listing, filtering, manual creation and
deletion. These endpoints are plain CRUD on those rows; the POST route is
the only writer today (the pipeline's ST-GCN++ results, NEM-5563, ride the
enrichment payload rather than this table).

The X-CLIP analyze endpoint (POST /api/action-events/analyze) was removed
with the full X-CLIP retirement (owner ruling 2026-09-23): frame classification
now runs as Triton stgcn_action via the ai-gateway, so there is no
on-demand frame analysis left to expose here.

Endpoints:
    GET    /api/action-events                      - List all action events
    GET    /api/action-events/suspicious           - List suspicious actions only
    GET    /api/action-events/{event_id}           - Get single action event
    GET    /api/action-events/camera/{camera_id}   - Get events for a camera
    POST   /api/action-events                      - Create an action event manually
    DELETE /api/action-events/{event_id}           - Delete an action event

Linear issue: NEM-3714
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.action_event import (
    ActionEventCreate,
    ActionEventListResponse,
    ActionEventResponse,
    SuspiciousActionsResponse,
)
from backend.api.schemas.pagination import PaginationMeta
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.models.action_event import ActionEvent

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


def _filtered_queries(
    camera_id: str | None,
    track_id: int | None,
    action: str | None,
    is_suspicious: bool | None,
    start_time: datetime | None,
    end_time: datetime | None,
    min_confidence: float | None,
) -> tuple:
    """Build (query, count_query) for action events with the given filters applied."""
    query = select(ActionEvent)
    count_query = select(func.count(ActionEvent.id))

    if camera_id is not None:
        query = query.where(ActionEvent.camera_id == camera_id)
        count_query = count_query.where(ActionEvent.camera_id == camera_id)

    if track_id is not None:
        query = query.where(ActionEvent.track_id == track_id)
        count_query = count_query.where(ActionEvent.track_id == track_id)

    if action is not None:
        query = query.where(ActionEvent.action == action)
        count_query = count_query.where(ActionEvent.action == action)

    if is_suspicious is not None:
        query = query.where(ActionEvent.is_suspicious == is_suspicious)
        count_query = count_query.where(ActionEvent.is_suspicious == is_suspicious)

    if start_time is not None:
        query = query.where(ActionEvent.timestamp >= start_time)
        count_query = count_query.where(ActionEvent.timestamp >= start_time)

    if end_time is not None:
        query = query.where(ActionEvent.timestamp <= end_time)
        count_query = count_query.where(ActionEvent.timestamp <= end_time)

    if min_confidence is not None:
        query = query.where(ActionEvent.confidence >= min_confidence)
        count_query = count_query.where(ActionEvent.confidence >= min_confidence)

    return query, count_query


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
    query, count_query = _filtered_queries(
        camera_id, track_id, action, is_suspicious, start_time, end_time, min_confidence
    )

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(ActionEvent.timestamp.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    events = list(result.scalars().all())

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
    query, count_query = _filtered_queries(
        camera_id, None, None, True, start_time, end_time, min_confidence
    )
    suspicious_result = await db.execute(count_query)
    suspicious_count = suspicious_result.scalar() or 0

    _, total_count_query = _filtered_queries(
        camera_id, None, None, None, start_time, end_time, min_confidence
    )
    total_result = await db.execute(total_count_query)
    total_count = total_result.scalar() or 0

    query = query.order_by(ActionEvent.timestamp.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    events = list(result.scalars().all())

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
    event = await db.get(ActionEvent, event_id)
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
        start_time: Filter by timestamp >= start time
        end_time: Filter by timestamp <= end time
        limit: Maximum number of results to return
        offset: Number of results to skip for pagination
        db: Database session

    Returns:
        ActionEventListResponse with events and pagination info
    """
    query, count_query = _filtered_queries(camera_id, None, None, None, start_time, end_time, None)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(ActionEvent.timestamp.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    events = list(result.scalars().all())

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
    timestamp = event_data.timestamp or datetime.now(UTC)

    event = ActionEvent(
        camera_id=event_data.camera_id,
        track_id=event_data.track_id,
        action=event_data.action,
        confidence=event_data.confidence,
        is_suspicious=event_data.is_suspicious,
        timestamp=timestamp,
        frame_count=event_data.frame_count,
        all_scores=event_data.all_scores,
    )

    db.add(event)
    await db.commit()
    await db.refresh(event)

    logger.info(
        f"Created action event: {event.id} - {event.action} "
        f"(confidence: {event.confidence:.2%}, suspicious: {event.is_suspicious})"
    )

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

    Raises:
        HTTPException: 404 if event not found
    """
    event = await db.get(ActionEvent, event_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action event {event_id} not found",
        )

    await db.delete(event)
    await db.commit()

    logger.info(f"Deleted action event: {event_id}")
