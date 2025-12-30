"""API routes for events management."""

import csv
import io
import json
from datetime import datetime
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.detections import DetectionListResponse
from backend.api.schemas.events import (
    EventListResponse,
    EventResponse,
    EventStatsResponse,
    EventUpdate,
)
from backend.api.schemas.search import SearchResponse as SearchResponseSchema
from backend.core.database import get_db
from backend.models.audit import AuditAction
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.services.audit import AuditService
from backend.services.search import SearchFilters, search_events

router = APIRouter(prefix="/api/events", tags=["events"])


def parse_detection_ids(detection_ids_str: str | None) -> list[int]:
    """Parse detection IDs stored as JSON array to list of integers.

    Args:
        detection_ids_str: JSON array string of detection IDs (e.g., "[1, 2, 3]")
                          or None/empty string

    Returns:
        List of integer detection IDs. Empty list if input is None or empty.
    """
    if not detection_ids_str:
        return []
    try:
        ids = json.loads(detection_ids_str)
        if isinstance(ids, list):
            return [int(d) for d in ids]
        return []
    except (json.JSONDecodeError, ValueError):
        # Fallback for legacy comma-separated format
        return [int(d.strip()) for d in detection_ids_str.split(",") if d.strip()]


@router.get("", response_model=EventListResponse)
async def list_events(  # noqa: PLR0912
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
    # We use a subquery approach to find matching event IDs, avoiding fragile LIKE patterns
    # that could incorrectly match partial IDs (e.g., "1" matching "10")
    matching_event_ids_for_object_type: set[int] | None = None
    if object_type:
        # Subquery to find detection IDs with matching object_type
        detection_ids_subquery = select(Detection.id).where(Detection.object_type == object_type)
        detection_ids_result = await db.execute(detection_ids_subquery)
        matching_detection_ids = set(detection_ids_result.scalars().all())

        if matching_detection_ids:
            # Find events that contain at least one of the matching detection IDs
            # We fetch all events and filter in Python to avoid fragile LIKE patterns
            # LIKE patterns like "[1,%" incorrectly match "[10,..." when searching for ID 1
            all_events_query = select(Event.id, Event.detection_ids)
            all_events_result = await db.execute(all_events_query)
            all_events = all_events_result.all()

            matching_event_ids_for_object_type = set()
            for event_id, detection_ids_str in all_events:
                # Parse the JSON array of detection IDs
                event_detection_ids = set(parse_detection_ids(detection_ids_str))
                # Check if any of the event's detection IDs match our target detection IDs
                if event_detection_ids & matching_detection_ids:
                    matching_event_ids_for_object_type.add(event_id)

            if matching_event_ids_for_object_type:
                query = query.where(Event.id.in_(matching_event_ids_for_object_type))
            else:
                # No matching events found, return empty result
                query = query.where(Event.id == -1)  # Impossible condition
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

    # Calculate detection count and parse detection_ids for each event
    events_with_counts = []
    for event in events:
        # Parse detection_ids (JSON array string) to list of integers
        parsed_detection_ids = parse_detection_ids(event.detection_ids)
        detection_count = len(parsed_detection_ids)

        # Create response with detection count and detection_ids
        event_dict = {
            "id": event.id,
            "camera_id": event.camera_id,
            "started_at": event.started_at,
            "ended_at": event.ended_at,
            "risk_score": event.risk_score,
            "risk_level": event.risk_level,
            "summary": event.summary,
            "reasoning": event.reasoning,
            "reviewed": event.reviewed,
            "detection_count": detection_count,
            "detection_ids": parsed_detection_ids,
        }
        events_with_counts.append(event_dict)

    return {
        "events": events_with_counts,
        "count": total_count,
        "limit": limit,
        "offset": offset,
    }


@router.get("/stats", response_model=EventStatsResponse)
async def get_event_stats(
    start_date: datetime | None = Query(None, description="Filter by start date (ISO format)"),
    end_date: datetime | None = Query(None, description="Filter by end date (ISO format)"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get aggregated event statistics.

    Returns statistics about events including:
    - Total event count
    - Events grouped by risk level (critical, high, medium, low)
    - Events grouped by camera with camera names

    Args:
        start_date: Optional start date for date range filter
        end_date: Optional end date for date range filter
        db: Database session

    Returns:
        EventStatsResponse with aggregated statistics
    """
    # Build base query with optional date filters
    query = select(Event)
    if start_date:
        query = query.where(Event.started_at >= start_date)
    if end_date:
        query = query.where(Event.started_at <= end_date)

    # Get all events matching filters
    result = await db.execute(query)
    events = result.scalars().all()

    # Calculate total events
    total_events = len(events)

    # Calculate events by risk level
    risk_level_counts = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
    }
    for event in events:
        if event.risk_level and event.risk_level in risk_level_counts:
            risk_level_counts[event.risk_level] += 1

    # Calculate events by camera
    camera_event_counts: dict[str, int] = {}
    for event in events:
        camera_event_counts[event.camera_id] = camera_event_counts.get(event.camera_id, 0) + 1

    # Get camera names
    camera_ids = list(camera_event_counts.keys())
    camera_query = select(Camera).where(Camera.id.in_(camera_ids))
    camera_result = await db.execute(camera_query)
    cameras = {camera.id: camera.name for camera in camera_result.scalars().all()}

    # Build events_by_camera list with camera names
    events_by_camera = [
        {
            "camera_id": camera_id,
            "camera_name": cameras.get(camera_id, "Unknown"),
            "event_count": count,
        }
        for camera_id, count in camera_event_counts.items()
    ]

    # Sort by event count descending
    events_by_camera.sort(key=lambda x: cast("int", x["event_count"]), reverse=True)

    return {
        "total_events": total_events,
        "events_by_risk_level": risk_level_counts,
        "events_by_camera": events_by_camera,
    }


@router.get("/search", response_model=SearchResponseSchema)
async def search_events_endpoint(
    q: str = Query(..., min_length=1, description="Search query string"),
    camera_id: str | None = Query(
        None, description="Filter by camera ID (comma-separated for multiple)"
    ),
    start_date: datetime | None = Query(None, description="Filter by start date (ISO format)"),
    end_date: datetime | None = Query(None, description="Filter by end date (ISO format)"),
    severity: str | None = Query(
        None, description="Filter by risk levels (comma-separated: low,medium,high,critical)"
    ),
    object_type: str | None = Query(
        None, description="Filter by object types (comma-separated: person,vehicle,animal)"
    ),
    reviewed: bool | None = Query(None, description="Filter by reviewed status"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Search events using full-text search.

    This endpoint provides PostgreSQL full-text search across event summaries,
    reasoning, object types, and camera names.

    Search Query Syntax:
    - Basic words: "person vehicle" (implicit AND)
    - Phrase search: '"suspicious person"' (exact phrase)
    - Boolean OR: "person OR animal"
    - Boolean NOT: "person NOT cat"
    - Boolean AND: "person AND vehicle" (explicit)

    Args:
        q: Search query string (required)
        camera_id: Optional comma-separated camera IDs to filter by
        start_date: Optional start date for date range filter
        end_date: Optional end date for date range filter
        severity: Optional comma-separated risk levels (low, medium, high, critical)
        object_type: Optional comma-separated object types (person, vehicle, animal)
        reviewed: Optional filter by reviewed status
        limit: Maximum number of results to return (1-1000, default 50)
        offset: Number of results to skip for pagination (default 0)
        db: Database session

    Returns:
        SearchResponse with ranked results and pagination info
    """
    # Parse comma-separated filter values
    camera_ids = [c.strip() for c in camera_id.split(",")] if camera_id else []
    severity_levels = [s.strip() for s in severity.split(",")] if severity else []
    object_types = [o.strip() for o in object_type.split(",")] if object_type else []

    # Build filters
    filters = SearchFilters(
        start_date=start_date,
        end_date=end_date,
        camera_ids=camera_ids,
        severity=severity_levels,
        object_types=object_types,
        reviewed=reviewed,
    )

    # Execute search
    search_response = await search_events(
        db=db,
        query=q,
        filters=filters,
        limit=limit,
        offset=offset,
    )

    # Convert to dict for response
    return {
        "results": [
            {
                "id": r.id,
                "camera_id": r.camera_id,
                "camera_name": r.camera_name,
                "started_at": r.started_at,
                "ended_at": r.ended_at,
                "risk_score": r.risk_score,
                "risk_level": r.risk_level,
                "summary": r.summary,
                "reasoning": r.reasoning,
                "reviewed": r.reviewed,
                "detection_count": r.detection_count,
                "detection_ids": r.detection_ids,
                "object_types": r.object_types,
                "relevance_score": r.relevance_score,
            }
            for r in search_response.results
        ],
        "total_count": search_response.total_count,
        "limit": search_response.limit,
        "offset": search_response.offset,
    }


@router.get("/export")
async def export_events(
    request: Request,
    camera_id: str | None = Query(None, description="Filter by camera ID"),
    risk_level: str | None = Query(
        None, description="Filter by risk level (low, medium, high, critical)"
    ),
    start_date: datetime | None = Query(None, description="Filter by start date (ISO format)"),
    end_date: datetime | None = Query(None, description="Filter by end date (ISO format)"),
    reviewed: bool | None = Query(None, description="Filter by reviewed status"),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Export events as CSV file for external analysis or record-keeping.

    Exports events with the following fields:
    - Event ID, camera name, timestamps
    - Risk score, risk level, summary
    - Detection count, reviewed status

    Args:
        camera_id: Optional camera ID to filter by
        risk_level: Optional risk level to filter by (low, medium, high, critical)
        start_date: Optional start date for date range filter
        end_date: Optional end date for date range filter
        reviewed: Optional filter by reviewed status
        db: Database session

    Returns:
        StreamingResponse with CSV file containing exported events
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

    # Sort by started_at descending (newest first)
    query = query.order_by(Event.started_at.desc())

    # Execute query
    result = await db.execute(query)
    events = result.scalars().all()

    # Get all camera IDs to fetch camera names
    camera_ids = {event.camera_id for event in events}
    camera_query = select(Camera).where(Camera.id.in_(camera_ids))
    camera_result = await db.execute(camera_query)
    cameras = {camera.id: camera.name for camera in camera_result.scalars().all()}

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(
        [
            "event_id",
            "camera_name",
            "started_at",
            "ended_at",
            "risk_score",
            "risk_level",
            "summary",
            "detection_count",
            "reviewed",
        ]
    )

    # Write event rows
    for event in events:
        camera_name = cameras.get(event.camera_id, "Unknown")
        detection_count = len(parse_detection_ids(event.detection_ids))

        # Format timestamps as ISO strings
        started_at_str = event.started_at.isoformat() if event.started_at else ""
        ended_at_str = event.ended_at.isoformat() if event.ended_at else ""

        writer.writerow(
            [
                event.id,
                camera_name,
                started_at_str,
                ended_at_str,
                event.risk_score if event.risk_score is not None else "",
                event.risk_level or "",
                event.summary or "",
                detection_count,
                "Yes" if event.reviewed else "No",
            ]
        )

    # Generate filename with timestamp
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"events_export_{timestamp}.csv"

    # Log the export action
    await AuditService.log_action(
        db=db,
        action=AuditAction.MEDIA_EXPORTED,
        resource_type="event",
        actor="anonymous",
        details={
            "export_type": "csv",
            "filters": {
                "camera_id": camera_id,
                "risk_level": risk_level,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
                "reviewed": reviewed,
            },
            "event_count": len(events),
            "filename": filename,
        },
        request=request,
    )
    await db.commit()

    # Return as streaming response with CSV content type
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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

    # Parse detection_ids and calculate count
    parsed_detection_ids = parse_detection_ids(event.detection_ids)
    detection_count = len(parsed_detection_ids)

    return {
        "id": event.id,
        "camera_id": event.camera_id,
        "started_at": event.started_at,
        "ended_at": event.ended_at,
        "risk_score": event.risk_score,
        "risk_level": event.risk_level,
        "summary": event.summary,
        "reasoning": event.reasoning,
        "reviewed": event.reviewed,
        "notes": event.notes,
        "detection_count": detection_count,
        "detection_ids": parsed_detection_ids,
    }


@router.patch("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: int,
    update_data: EventUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Update an event (mark as reviewed).

    Args:
        event_id: Event ID
        update_data: Update data (reviewed field)
        request: FastAPI request for audit logging
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

    # Track changes for audit log
    changes: dict[str, Any] = {}
    old_reviewed = event.reviewed
    old_notes = event.notes

    # Update fields if provided (use exclude_unset to differentiate between None and not provided)
    update_dict = update_data.model_dump(exclude_unset=True)
    if "reviewed" in update_dict and update_data.reviewed is not None:
        event.reviewed = update_data.reviewed
        if old_reviewed != event.reviewed:
            changes["reviewed"] = {"old": old_reviewed, "new": event.reviewed}
    if "notes" in update_dict:
        event.notes = update_data.notes
        if old_notes != event.notes:
            changes["notes"] = {"old": old_notes, "new": event.notes}

    # Determine audit action based on changes
    if changes.get("reviewed", {}).get("new") is True:
        action = AuditAction.EVENT_REVIEWED
    elif changes.get("reviewed", {}).get("new") is False:
        action = AuditAction.EVENT_DISMISSED
    else:
        action = AuditAction.EVENT_REVIEWED  # Default for notes-only updates

    # Log the audit entry
    await AuditService.log_action(
        db=db,
        action=action,
        resource_type="event",
        resource_id=str(event_id),
        actor="anonymous",  # No auth in this system
        details={
            "changes": changes,
            "risk_level": event.risk_level,
            "camera_id": event.camera_id,
        },
        request=request,
    )

    await db.commit()
    await db.refresh(event)

    # Parse detection_ids and calculate count
    parsed_detection_ids = parse_detection_ids(event.detection_ids)
    detection_count = len(parsed_detection_ids)

    return {
        "id": event.id,
        "camera_id": event.camera_id,
        "started_at": event.started_at,
        "ended_at": event.ended_at,
        "risk_score": event.risk_score,
        "risk_level": event.risk_level,
        "summary": event.summary,
        "reasoning": event.reasoning,
        "reviewed": event.reviewed,
        "notes": event.notes,
        "detection_count": detection_count,
        "detection_ids": parsed_detection_ids,
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

    # Parse detection_ids using helper function
    detection_ids = parse_detection_ids(event.detection_ids)

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
