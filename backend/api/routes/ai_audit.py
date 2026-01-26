"""API routes for AI pipeline audit management.

This module provides endpoints for auditing AI pipeline performance,
including model contributions, quality scores, and recommendations.

Note: Prompt management endpoints have been consolidated into
backend/api/routes/prompt_management.py (NEM-2695).
"""

from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import (
    get_event_audit_or_404,
    get_event_or_404,
    get_job_tracker_dep,
)
from backend.api.schemas.ai_audit import (
    AuditStatsResponse,
    BatchAuditJobResponse,
    BatchAuditJobStatusResponse,
    BatchAuditRequest,
    EventAuditResponse,
    LeaderboardResponse,
    ModelContributions,
    ModelLeaderboardEntry,
    PromptImprovements,
    QualityScores,
    RecommendationItem,
    RecommendationsResponse,
)
from backend.core.database import get_db, get_session
from backend.core.json_utils import safe_json_loads
from backend.core.logging import get_logger, sanitize_log_value
from backend.models.audit import AuditAction
from backend.models.event import Event
from backend.models.event_audit import EventAudit
from backend.services.audit import AuditService
from backend.services.job_tracker import JobTracker
from backend.services.pipeline_quality_audit_service import get_audit_service

logger = get_logger(__name__)


def safe_parse_datetime(value: str | None, fallback: datetime | None = None) -> datetime:
    """Safely parse an ISO format datetime string.

    Handles malformed timestamps gracefully by returning a fallback value
    and logging a warning.

    Args:
        value: ISO format datetime string to parse
        fallback: Datetime to return if parsing fails (defaults to now UTC)

    Returns:
        Parsed datetime or fallback value
    """
    if fallback is None:
        fallback = datetime.now(UTC)
    if not value:
        return fallback
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        logger.warning(f"Invalid datetime format: {sanitize_log_value(value)}, using fallback")
        return fallback


router = APIRouter(prefix="/api/ai-audit", tags=["ai-audit"])


def _audit_to_response(audit: EventAudit) -> EventAuditResponse:
    """Convert an EventAudit model to EventAuditResponse schema.

    Handles nested objects (contributions, scores, improvements) and
    JSON-encoded fields.

    Args:
        audit: EventAudit model instance

    Returns:
        EventAuditResponse schema instance
    """
    # Build model contributions
    contributions = ModelContributions(
        yolo26=audit.has_yolo26,
        florence=audit.has_florence,
        clip=audit.has_clip,
        violence=audit.has_violence,
        clothing=audit.has_clothing,
        vehicle=audit.has_vehicle,
        pet=audit.has_pet,
        weather=audit.has_weather,
        image_quality=audit.has_image_quality,
        zones=audit.has_zones,
        baseline=audit.has_baseline,
        cross_camera=audit.has_cross_camera,
    )

    # Build quality scores
    scores = QualityScores(
        context_usage=audit.context_usage_score,
        reasoning_coherence=audit.reasoning_coherence_score,
        risk_justification=audit.risk_justification_score,
        consistency=audit.consistency_score,
        overall=audit.overall_quality_score,
    )

    # Parse JSON fields for improvements using safe_json_loads for error context
    def _parse_json_list(json_str: str | None, field_name: str) -> list[str]:
        if not json_str:
            return []
        result = safe_json_loads(
            json_str,
            default=[],
            context=f"EventAudit.{field_name} (audit_id={audit.id})",
        )
        return result if isinstance(result, list) else []

    improvements = PromptImprovements(
        missing_context=_parse_json_list(audit.missing_context, "missing_context"),
        confusing_sections=_parse_json_list(audit.confusing_sections, "confusing_sections"),
        unused_data=_parse_json_list(audit.unused_data, "unused_data"),
        format_suggestions=_parse_json_list(audit.format_suggestions, "format_suggestions"),
        model_gaps=_parse_json_list(audit.model_gaps, "model_gaps"),
    )

    return EventAuditResponse(
        id=audit.id,
        event_id=audit.event_id,
        audited_at=audit.audited_at,
        is_fully_evaluated=audit.is_fully_evaluated,
        contributions=contributions,
        prompt_length=audit.prompt_length,
        prompt_token_estimate=audit.prompt_token_estimate,
        enrichment_utilization=audit.enrichment_utilization,
        scores=scores,
        consistency_risk_score=audit.consistency_risk_score,
        consistency_diff=audit.consistency_diff,
        self_eval_critique=audit.self_eval_critique,
        improvements=improvements,
    )


@router.get(
    "/events/{event_id}",
    response_model=EventAuditResponse,
    responses={
        404: {"description": "Event or audit not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_event_audit(
    event_id: int,
    db: AsyncSession = Depends(get_db),
) -> EventAuditResponse:
    """Get audit information for a specific event.

    Retrieves the AI pipeline audit record for the given event, including
    model contributions, quality scores, and prompt improvement suggestions.

    Args:
        event_id: The ID of the event to get audit for
        db: Database session

    Returns:
        EventAuditResponse containing full audit details

    Raises:
        HTTPException: 404 if event or audit not found
    """
    # Check if event exists
    await get_event_or_404(event_id, db)

    # Get audit for event
    audit = await get_event_audit_or_404(event_id, db)

    return _audit_to_response(audit)


@router.post(
    "/events/{event_id}/evaluate",
    response_model=EventAuditResponse,
    responses={
        404: {"description": "Event or audit not found"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def evaluate_event(
    event_id: int,
    request: Request,
    force: bool = Query(False, description="Force re-evaluation even if already evaluated"),
    db: AsyncSession = Depends(get_db),
) -> EventAuditResponse:
    """Trigger full evaluation for a specific event's audit.

    Runs the complete self-evaluation pipeline (self-critique, rubric scoring,
    consistency check, prompt improvement) for the given event.

    Args:
        event_id: The ID of the event to evaluate
        request: HTTP request for audit logging
        force: If True, re-evaluate even if already evaluated
        db: Database session

    Returns:
        EventAuditResponse with updated evaluation results

    Raises:
        HTTPException: 404 if event or audit not found
    """
    # Check if event exists
    event = await get_event_or_404(event_id, db)

    # Get audit for event
    audit = await get_event_audit_or_404(event_id, db)

    # Skip if already evaluated and not forcing
    if audit.is_fully_evaluated and not force:
        return _audit_to_response(audit)

    # Run full evaluation
    service = get_audit_service()
    updated_audit = await service.run_full_evaluation(audit, event, db)

    # Log the audit entry for AI re-evaluation (actor auto-derived from request)
    await AuditService.log_action(
        db=db,
        action=AuditAction.AI_REEVALUATED,
        resource_type="event",
        resource_id=str(event_id),
        details={
            "is_force": force,
            "overall_quality_score": updated_audit.overall_quality_score,
        },
        request=request,
    )
    await db.commit()

    return _audit_to_response(updated_audit)


@router.get(
    "/stats",
    response_model=AuditStatsResponse,
    responses={
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def get_audit_stats(
    days: int = Query(7, ge=1, le=90, description="Number of days to include"),
    camera_id: str | None = Query(None, description="Filter by camera ID"),
    db: AsyncSession = Depends(get_db),
) -> AuditStatsResponse:
    """Get aggregate AI audit statistics.

    Returns aggregate statistics including total events, quality scores,
    model contribution rates, and audit trends over the specified period.

    Args:
        days: Number of days to include in statistics (1-90, default 7)
        camera_id: Optional camera ID to filter stats
        db: Database session

    Returns:
        AuditStatsResponse with aggregate statistics
    """
    service = get_audit_service()
    stats = await service.get_stats(db, days=days, camera_id=camera_id)

    return AuditStatsResponse(
        total_events=stats["total_events"],
        audited_events=stats["audited_events"],
        fully_evaluated_events=stats["fully_evaluated_events"],
        avg_quality_score=stats["avg_quality_score"],
        avg_consistency_rate=stats["avg_consistency_rate"],
        avg_enrichment_utilization=stats["avg_enrichment_utilization"],
        model_contribution_rates=stats["model_contribution_rates"],
        audits_by_day=stats["audits_by_day"],
    )


@router.get(
    "/leaderboard",
    response_model=LeaderboardResponse,
    responses={
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def get_model_leaderboard(
    days: int = Query(7, ge=1, le=90, description="Number of days to include"),
    db: AsyncSession = Depends(get_db),
) -> LeaderboardResponse:
    """Get model leaderboard ranked by contribution rate.

    Returns a ranked list of AI models by their contribution rate,
    along with quality correlation data.

    Args:
        days: Number of days to include (1-90, default 7)
        db: Database session

    Returns:
        LeaderboardResponse with ranked model entries
    """
    service = get_audit_service()
    entries = await service.get_leaderboard(db, days=days)

    return LeaderboardResponse(
        entries=[
            ModelLeaderboardEntry(
                model_name=entry["model_name"],
                contribution_rate=entry["contribution_rate"],
                quality_correlation=entry["quality_correlation"],
                event_count=entry["event_count"],
            )
            for entry in entries
        ],
        period_days=days,
    )


@router.get(
    "/recommendations",
    response_model=RecommendationsResponse,
    responses={
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def get_recommendations(
    days: int = Query(7, ge=1, le=90, description="Number of days to include"),
    db: AsyncSession = Depends(get_db),
) -> RecommendationsResponse:
    """Get aggregated prompt improvement recommendations.

    Analyzes all audits to produce actionable recommendations for
    improving the AI pipeline prompt templates.

    Args:
        days: Number of days to analyze (1-90, default 7)
        db: Database session

    Returns:
        RecommendationsResponse with prioritized recommendations
    """
    service = get_audit_service()
    recommendations = await service.get_recommendations(db, days=days)

    # Count total events analyzed (approximate from service stats)
    stats = await service.get_stats(db, days=days)

    return RecommendationsResponse(
        recommendations=[
            RecommendationItem(
                category=rec["category"],
                suggestion=rec["suggestion"],
                frequency=rec["frequency"],
                priority=rec["priority"],
            )
            for rec in recommendations
        ],
        total_events_analyzed=stats["fully_evaluated_events"],
    )


async def _run_batch_audit_job(
    job_id: str,
    event_ids: list[int],
    force_reevaluate: bool,
    job_tracker: JobTracker,
) -> None:
    """Background task for processing batch audit.

    This function runs in the background after the endpoint returns,
    processing events one at a time with progress updates.

    Args:
        job_id: The job ID for tracking progress
        event_ids: List of event IDs to process
        force_reevaluate: Whether to force re-evaluation
        job_tracker: Job tracker for progress updates
    """
    total_events = len(event_ids)
    processed_events = 0
    failed_events = 0

    try:
        # Mark job as started
        job_tracker.start_job(job_id, message=f"Starting batch audit of {total_events} events...")

        # Get a fresh database session for background processing
        async with get_session() as db:
            # Get audit service for processing
            service = get_audit_service()

            for i, event_id in enumerate(event_ids):
                try:
                    # Update progress
                    progress = int((i / total_events) * 100)
                    job_tracker.update_progress(
                        job_id,
                        progress,
                        message=f"Processing event {i + 1} of {total_events}",
                    )

                    # Fetch the event
                    result = await db.execute(select(Event).where(Event.id == event_id))
                    event = result.scalar_one_or_none()

                    if event is None:
                        logger.warning(
                            f"Event {event_id} not found during batch audit",
                            extra={"job_id": job_id, "event_id": event_id},
                        )
                        failed_events += 1
                        continue

                    # Check if audit exists
                    audit_result = await db.execute(
                        select(EventAudit).where(EventAudit.event_id == event_id)
                    )
                    audit = audit_result.scalar_one_or_none()

                    if audit is None:
                        # Create partial audit if missing
                        audit = service.create_partial_audit(
                            event_id=event.id,
                            llm_prompt=event.llm_prompt,
                            enriched_context=None,
                            enrichment_result=None,
                        )
                        db.add(audit)
                        await db.commit()
                        await db.refresh(audit)

                    # Skip if already evaluated and not forcing
                    if audit.is_fully_evaluated and not force_reevaluate:
                        processed_events += 1
                        continue

                    # Run evaluation
                    await service.run_full_evaluation(audit, event, db)
                    processed_events += 1

                except Exception as e:
                    logger.exception(
                        f"Error processing event {event_id} in batch audit",
                        extra={"job_id": job_id, "event_id": event_id, "error": str(e)},
                    )
                    failed_events += 1

        # Complete the job with result
        job_tracker.complete_job(
            job_id,
            result={
                "total_events": total_events,
                "processed_events": processed_events,
                "failed_events": failed_events,
            },
        )

        logger.info(
            "Batch audit job completed",
            extra={
                "job_id": job_id,
                "total": total_events,
                "processed": processed_events,
                "failed": failed_events,
            },
        )

    except Exception as e:
        logger.exception("Batch audit job failed", extra={"job_id": job_id})
        job_tracker.fail_job(job_id, str(e))


@router.post(
    "/batch",
    response_model=BatchAuditJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: {"description": "Batch audit job created successfully"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def trigger_batch_audit(
    request: BatchAuditRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    job_tracker: JobTracker = Depends(get_job_tracker_dep),
) -> BatchAuditJobResponse:
    """Trigger batch audit processing for multiple events.

    This endpoint returns immediately with a job ID that can be used to
    track progress via GET /api/ai-audit/batch/{job_id}. Events are
    processed asynchronously in the background.

    Args:
        request: Batch audit request with filtering criteria
        background_tasks: FastAPI background tasks
        db: Database session
        job_tracker: Job tracker for progress tracking

    Returns:
        BatchAuditJobResponse with job ID for tracking progress
    """
    # Build query for events needing audit
    query = select(Event).outerjoin(EventAudit)

    if not request.force_reevaluate:
        # Only events without full evaluation
        query = query.where(
            (EventAudit.id.is_(None)) | (EventAudit.overall_quality_score.is_(None))
        )

    if request.min_risk_score is not None:
        query = query.where(Event.risk_score >= request.min_risk_score)

    query = query.limit(request.limit)

    result = await db.execute(query)
    events = result.scalars().all()

    if not events:
        # No events to process - return immediately with zero count
        # Still create a job for consistency, but mark it as complete
        job_id = job_tracker.create_job("batch_audit")
        job_tracker.start_job(job_id, message="No events found matching criteria")
        job_tracker.complete_job(
            job_id,
            result={
                "total_events": 0,
                "processed_events": 0,
                "failed_events": 0,
            },
        )
        return BatchAuditJobResponse(
            job_id=job_id,
            status="completed",
            message="No events found matching criteria",
            total_events=0,
        )

    # Create job for tracking
    job_id = job_tracker.create_job("batch_audit")

    # Extract event IDs for background processing
    event_ids = [event.id for event in events]

    # Schedule background task
    background_tasks.add_task(
        _run_batch_audit_job,
        job_id=job_id,
        event_ids=event_ids,
        force_reevaluate=request.force_reevaluate,
        job_tracker=job_tracker,
    )

    logger.info(
        "Batch audit job created",
        extra={"job_id": job_id, "event_count": len(event_ids)},
    )

    return BatchAuditJobResponse(
        job_id=job_id,
        status="pending",
        message=f"Batch audit job created. Use GET /api/ai-audit/batch/{job_id} to track progress.",
        total_events=len(event_ids),
    )


@router.get(
    "/batch/{job_id}",
    response_model=BatchAuditJobStatusResponse,
    responses={
        404: {"description": "Job not found"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def get_batch_audit_status(
    job_id: str,
    job_tracker: JobTracker = Depends(get_job_tracker_dep),
) -> BatchAuditJobStatusResponse:
    """Get the status of a batch audit job.

    Provides progress information for an ongoing or completed batch audit,
    including the number of events processed and any errors.

    Args:
        job_id: The job ID returned by trigger_batch_audit
        job_tracker: Job tracker for retrieving job status

    Returns:
        BatchAuditJobStatusResponse with current progress

    Raises:
        HTTPException: 404 if job not found
    """
    # Try in-memory first, then Redis
    job = job_tracker.get_job(job_id)

    if job is None:
        # Try Redis for completed/failed jobs
        job = await job_tracker.get_job_from_redis(job_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No batch audit job found with ID: {job_id}",
        )

    # Extract result data if available
    result = job.get("result") or {}
    total_events = result.get("total_events", 0)
    processed_events = result.get("processed_events", 0)
    failed_events = result.get("failed_events", 0)

    # Parse timestamps
    created_at_str = job.get("created_at")
    started_at_str = job.get("started_at")
    completed_at_str = job.get("completed_at")

    created_at = safe_parse_datetime(created_at_str, datetime.now(UTC))
    started_at = safe_parse_datetime(started_at_str) if started_at_str else None
    completed_at = safe_parse_datetime(completed_at_str) if completed_at_str else None

    return BatchAuditJobStatusResponse(
        job_id=job_id,
        status=str(job.get("status", "unknown")),
        progress=job.get("progress", 0),
        message=job.get("message"),
        total_events=total_events,
        processed_events=processed_events,
        failed_events=failed_events,
        created_at=created_at,
        started_at=started_at,
        completed_at=completed_at,
        error=job.get("error"),
    )
