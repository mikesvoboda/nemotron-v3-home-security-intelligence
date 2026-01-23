"""API routes for event feedback management.

NEM-1908: Create EventFeedback API schemas and routes
NEM-3330: Enhanced feedback fields for Nemotron prompt improvement

Provides endpoints for:
- Submitting user feedback on events (false positives, missed detections, etc.)
- Retrieving feedback for specific events
- Getting aggregate feedback statistics for model calibration

Enhanced fields (NEM-3330):
- actual_threat_level: User's assessment of true threat level
- suggested_score: What the user thinks the score should have been
- actual_identity: Identity correction for household member learning
- what_was_wrong: Detailed explanation of AI failure
- model_failures: List of specific AI models that failed
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.feedback import (
    EventFeedbackCreate,
    EventFeedbackResponse,
    FeedbackStatsResponse,
)
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.models.event import Event
from backend.models.event_feedback import EventFeedback

logger = get_logger(__name__)
router = APIRouter(prefix="/api/feedback", tags=["feedback"])


@router.post(
    "",
    response_model=EventFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit event feedback",
    responses={
        201: {"description": "Feedback created successfully"},
        404: {"description": "Event not found"},
        409: {"description": "Feedback already exists for this event"},
        422: {"description": "Validation error"},
    },
)
async def create_feedback(
    feedback_data: EventFeedbackCreate,
    db: AsyncSession = Depends(get_db),
) -> EventFeedbackResponse:
    """Submit feedback for an event.

    Allows users to mark events as false positives, missed detections,
    wrong severity, or correctly classified. Only one feedback per event
    is allowed (enforced by unique constraint).

    This feedback is used to calibrate personalized risk thresholds
    and improve the AI model's accuracy over time.

    Args:
        feedback_data: Feedback details including event_id and feedback_type
        db: Database session

    Returns:
        The created feedback record

    Raises:
        HTTPException: 404 if event not found
        HTTPException: 409 if feedback already exists for this event
    """
    # Check if event exists
    event_query = select(Event).where(Event.id == feedback_data.event_id)
    event_result = await db.execute(event_query)
    event = event_result.scalar_one_or_none()

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with ID {feedback_data.event_id} not found",
        )

    # Check if feedback already exists for this event (prevent duplicates)
    existing_query = select(EventFeedback).where(EventFeedback.event_id == feedback_data.event_id)
    existing_result = await db.execute(existing_query)
    existing_feedback = existing_result.scalar_one_or_none()

    if existing_feedback is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Feedback already exists for event {feedback_data.event_id}",
        )

    # Create feedback record with enhanced fields (NEM-3330)
    feedback = EventFeedback(
        event_id=feedback_data.event_id,
        feedback_type=feedback_data.feedback_type,
        notes=feedback_data.notes,
        # Enhanced fields for Nemotron prompt improvement
        actual_threat_level=(
            feedback_data.actual_threat_level.value if feedback_data.actual_threat_level else None
        ),
        suggested_score=feedback_data.suggested_score,
        actual_identity=feedback_data.actual_identity,
        what_was_wrong=feedback_data.what_was_wrong,
        model_failures=feedback_data.model_failures,
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)

    logger.info(
        f"Feedback submitted for event {feedback_data.event_id}: {feedback_data.feedback_type}",
        extra={
            "event_id": feedback_data.event_id,
            "feedback_type": feedback_data.feedback_type.value,
            "camera_id": event.camera_id,
            "actual_threat_level": feedback.actual_threat_level,
            "suggested_score": feedback.suggested_score,
            "actual_identity": feedback.actual_identity,
        },
    )

    return EventFeedbackResponse(
        id=feedback.id,
        event_id=feedback.event_id,
        feedback_type=feedback.feedback_type,
        notes=feedback.notes,
        actual_threat_level=feedback.actual_threat_level,
        suggested_score=feedback.suggested_score,
        actual_identity=feedback.actual_identity,
        what_was_wrong=feedback.what_was_wrong,
        model_failures=feedback.model_failures,
        created_at=feedback.created_at,
    )


@router.get(
    "/event/{event_id}",
    response_model=EventFeedbackResponse,
    summary="Get feedback for an event",
    responses={
        200: {"description": "Feedback found"},
        404: {"description": "No feedback found for this event"},
        422: {"description": "Validation error"},
    },
)
async def get_event_feedback(
    event_id: int,
    db: AsyncSession = Depends(get_db),
) -> EventFeedbackResponse:
    """Get feedback for a specific event.

    Args:
        event_id: The event ID to get feedback for
        db: Database session

    Returns:
        The feedback record for the event

    Raises:
        HTTPException: 404 if no feedback exists for the event
    """
    query = select(EventFeedback).where(EventFeedback.event_id == event_id)
    result = await db.execute(query)
    feedback = result.scalar_one_or_none()

    if feedback is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No feedback found for event {event_id}",
        )

    return EventFeedbackResponse(
        id=feedback.id,
        event_id=feedback.event_id,
        feedback_type=feedback.feedback_type,
        notes=feedback.notes,
        actual_threat_level=feedback.actual_threat_level,
        suggested_score=feedback.suggested_score,
        actual_identity=feedback.actual_identity,
        what_was_wrong=feedback.what_was_wrong,
        model_failures=feedback.model_failures,
        created_at=feedback.created_at,
    )


@router.get(
    "/stats",
    response_model=FeedbackStatsResponse,
    summary="Get feedback statistics",
    responses={
        200: {"description": "Statistics retrieved successfully"},
    },
)
async def get_feedback_stats(
    db: AsyncSession = Depends(get_db),
) -> FeedbackStatsResponse:
    """Get aggregate feedback statistics.

    Returns counts of feedback grouped by:
    - Feedback type (false_positive, missed_detection, wrong_severity, correct)
    - Camera ID

    This data is useful for:
    - Identifying cameras with high false positive rates
    - Calibrating risk thresholds per camera
    - Tracking model accuracy over time

    Args:
        db: Database session

    Returns:
        Aggregate statistics including total count and breakdowns
    """
    # Get total count
    count_query = select(func.count(EventFeedback.id))
    count_result = await db.execute(count_query)
    total_feedback = count_result.scalar() or 0

    # Get counts by feedback type
    type_query = select(EventFeedback.feedback_type, func.count(EventFeedback.id)).group_by(
        EventFeedback.feedback_type
    )
    type_result = await db.execute(type_query)
    by_type = {str(feedback_type): count for feedback_type, count in type_result.all()}

    # Get counts by camera (join with Event to get camera_id)
    camera_query = (
        select(Event.camera_id, func.count(EventFeedback.id))
        .join(Event, EventFeedback.event_id == Event.id)
        .group_by(Event.camera_id)
    )
    camera_result = await db.execute(camera_query)
    by_camera: dict[str, int] = {
        str(camera_id): int(count) for camera_id, count in camera_result.all()
    }

    return FeedbackStatsResponse(
        total_feedback=total_feedback,
        by_type=by_type,
        by_camera=by_camera,
    )
