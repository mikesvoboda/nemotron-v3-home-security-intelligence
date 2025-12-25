"""API routes for events management."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.detections import DetectionListResponse
from backend.api.schemas.events import EventListResponse, EventResponse, EventUpdate
from backend.core.database import get_db
from backend.models.detection import Detection
from backend.models.event import Event

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("", response_model=EventListResponse)
async def list_events(
    camera_id: str | None = Query(None, description="Filter by camera ID"),
    risk_level: str | None = Query(
        None, description="Filter by risk level (low, medium, high, critical)"
    ),
    start_date: datetime | None = Query(None, description="Filter by start date (ISO format)"),
    end_date: datetime | None = Query(None, description="Filter by end date (ISO format)"),
    reviewed: bool | None = Query(None, description="Filter by reviewed status"),
    object_type: str | None = Query(None, description="Filter by detected object type"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List events with optional filtering and pagination.

    Args:
        camera_id: Optional camera ID to filter by
        risk_level: Optional risk level to filter by (low, medium, high, critical)
        start_date: Optional start date for date range filter
        end_date: Optional end date for date range filter
        reviewed: Optional filter by reviewed status
        object_type: Optional object type to filter by (person, vehicle, animal, etc.)
        limit: Maximum number of results to return (1-1000, default 50)
        offset: Number of results to skip for pagination (default 0)
        db: Database session

    Returns:
        EventListResponse containing filtered events and pagination info
    """
    # Build base query
    query = select(Event)

    # Apply filters
    if camera_id:
        query = query.where(Event.camera_id == camera_id)
    if risk_level:
        query = query.where(Event.risk_level == risk_level)
    if start_date:
        query = query.where(Event.started_at >= start_date)
    if end_date:
        query = query.where(Event.started_at <= end_date)
    if reviewed is not None:
        query = query.where(Event.reviewed == reviewed)

    # Filter by object type - find events that have at least one detection with this type
    if object_type:
        # Subquery to find detection IDs with matching object_type
        detection_ids_subquery = select(Detection.id).where(Detection.object_type == object_type)
        detection_ids_result = await db.execute(detection_ids_subquery)
        matching_detection_ids = {str(d) for d in detection_ids_result.scalars().all()}

        if matching_detection_ids:
            # Filter events where detection_ids contains at least one matching ID
            conditions = []
            for det_id in matching_detection_ids:
                # Match: "id,", ",id,", ",id" or just "id"
                conditions.extend(
                    [
                        Event.detection_ids.like(f"{det_id},%"),
                        Event.detection_ids.like(f"%,{det_id},%"),
                        Event.detection_ids.like(f"%,{det_id}"),
                        Event.detection_ids == det_id,
                    ]
                )
            query = query.where(or_(*conditions))
        else:
            # No matching detections found, return empty result
            query = query.where(Event.id == -1)  # Impossible condition

    # Get total count (before pagination)
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Sort by started_at descending (newest first)
    query = query.order_by(Event.started_at.desc())

    # Apply pagination
    query = query.limit(limit).offset(offset)

    # Execute query
    result = await db.execute(query)
    events = result.scalars().all()

    # Calculate detection count for each event
    events_with_counts = []
    for event in events:
        # Parse detection_ids (comma-separated string) to count detections
        detection_count = 0
        if event.detection_ids:
            detection_count = len([d for d in event.detection_ids.split(",") if d.strip()])

        # Create response with detection count
        event_dict = {
            "id": event.id,
            "camera_id": event.camera_id,
            "started_at": event.started_at,
            "ended_at": event.ended_at,
            "risk_score": event.risk_score,
            "risk_level": event.risk_level,
            "summary": event.summary,
            "reviewed": event.reviewed,
            "detection_count": detection_count,
        }
        events_with_counts.append(event_dict)

    return {
        "events": events_with_counts,
        "count": total_count,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get a specific event by ID.

    Args:
        event_id: Event ID
        db: Database session

    Returns:
        Event object with detection count

    Raises:
        HTTPException: 404 if event not found
    """
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with id {event_id} not found",
        )

    # Calculate detection count
    detection_count = 0
    if event.detection_ids:
        detection_count = len([d for d in event.detection_ids.split(",") if d.strip()])

    return {
        "id": event.id,
        "camera_id": event.camera_id,
        "started_at": event.started_at,
        "ended_at": event.ended_at,
        "risk_score": event.risk_score,
        "risk_level": event.risk_level,
        "summary": event.summary,
        "reviewed": event.reviewed,
        "detection_count": detection_count,
    }


@router.patch("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: int,
    update_data: EventUpdate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Update an event (mark as reviewed).

    Args:
        event_id: Event ID
        update_data: Update data (reviewed field)
        db: Database session

    Returns:
        Updated event object

    Raises:
        HTTPException: 404 if event not found
    """
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with id {event_id} not found",
        )

    # Update fields if provided
    if update_data.reviewed is not None:
        event.reviewed = update_data.reviewed
    if update_data.notes is not None:
        event.notes = update_data.notes
    await db.commit()
    await db.refresh(event)

    # Calculate detection count
    detection_count = 0
    if event.detection_ids:
        detection_count = len([d for d in event.detection_ids.split(",") if d.strip()])

    return {
        "id": event.id,
        "camera_id": event.camera_id,
        "started_at": event.started_at,
        "ended_at": event.ended_at,
        "risk_score": event.risk_score,
        "risk_level": event.risk_level,
        "summary": event.summary,
        "reviewed": event.reviewed,
        "notes": event.notes,
        "detection_count": detection_count,
    }


@router.get("/{event_id}/detections", response_model=DetectionListResponse)
async def get_event_detections(
    event_id: int,
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get detections for a specific event.

    Args:
        event_id: Event ID
        limit: Maximum number of results to return (1-1000, default 50)
        offset: Number of results to skip for pagination (default 0)
        db: Database session

    Returns:
        DetectionListResponse containing detections for the event

    Raises:
        HTTPException: 404 if event not found
    """
    # Get event to verify it exists and get detection_ids
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with id {event_id} not found",
        )

    # Parse detection_ids (comma-separated string)
    detection_ids = []
    if event.detection_ids:
        detection_ids = [int(d.strip()) for d in event.detection_ids.split(",") if d.strip()]

    # If no detections, return empty list
    if not detection_ids:
        return {
            "detections": [],
            "count": 0,
            "limit": limit,
            "offset": offset,
        }

    # Build query for detections
    query = select(Detection).where(Detection.id.in_(detection_ids))

    # Get total count (before pagination)
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Sort by detected_at ascending (chronological order within event)
    query = query.order_by(Detection.detected_at.asc())

    # Apply pagination
    query = query.limit(limit).offset(offset)

    # Execute query
    result = await db.execute(query)
    detections = result.scalars().all()

    return {
        "detections": detections,
        "count": total_count,
        "limit": limit,
        "offset": offset,
    }
