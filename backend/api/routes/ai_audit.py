"""API routes for AI pipeline audit management.

This module provides endpoints for auditing AI pipeline performance,
including model contributions, quality scores, and recommendations.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.ai_audit import (
    AuditStatsResponse,
    BatchAuditRequest,
    BatchAuditResponse,
    EventAuditResponse,
    LeaderboardResponse,
    ModelContributions,
    ModelLeaderboardEntry,
    PromptImprovements,
    QualityScores,
    RecommendationItem,
    RecommendationsResponse,
)
from backend.core.database import get_db
from backend.models.event import Event
from backend.models.event_audit import EventAudit
from backend.services.audit_service import get_audit_service

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
        rtdetr=audit.has_rtdetr,
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

    # Parse JSON fields for improvements
    def _parse_json_list(json_str: str | None) -> list[str]:
        if not json_str:
            return []
        try:
            result = json.loads(json_str)
            return result if isinstance(result, list) else []
        except json.JSONDecodeError:
            return []

    improvements = PromptImprovements(
        missing_context=_parse_json_list(audit.missing_context),
        confusing_sections=_parse_json_list(audit.confusing_sections),
        unused_data=_parse_json_list(audit.unused_data),
        format_suggestions=_parse_json_list(audit.format_suggestions),
        model_gaps=_parse_json_list(audit.model_gaps),
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


@router.get("/events/{event_id}", response_model=EventAuditResponse)
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
    event_result = await db.execute(select(Event).where(Event.id == event_id))
    event = event_result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} not found",
        )

    # Get audit for event
    audit_result = await db.execute(select(EventAudit).where(EventAudit.event_id == event_id))
    audit = audit_result.scalar_one_or_none()

    if not audit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No audit found for event {event_id}",
        )

    return _audit_to_response(audit)


@router.post("/events/{event_id}/evaluate", response_model=EventAuditResponse)
async def evaluate_event(
    event_id: int,
    force: bool = Query(False, description="Force re-evaluation even if already evaluated"),
    db: AsyncSession = Depends(get_db),
) -> EventAuditResponse:
    """Trigger full evaluation for a specific event's audit.

    Runs the complete self-evaluation pipeline (self-critique, rubric scoring,
    consistency check, prompt improvement) for the given event.

    Args:
        event_id: The ID of the event to evaluate
        force: If True, re-evaluate even if already evaluated
        db: Database session

    Returns:
        EventAuditResponse with updated evaluation results

    Raises:
        HTTPException: 404 if event or audit not found
    """
    # Check if event exists
    event_result = await db.execute(select(Event).where(Event.id == event_id))
    event = event_result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} not found",
        )

    # Get audit for event
    audit_result = await db.execute(select(EventAudit).where(EventAudit.event_id == event_id))
    audit = audit_result.scalar_one_or_none()

    if not audit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No audit found for event {event_id}",
        )

    # Skip if already evaluated and not forcing
    if audit.is_fully_evaluated and not force:
        return _audit_to_response(audit)

    # Run full evaluation
    service = get_audit_service()
    updated_audit = await service.run_full_evaluation(audit, event, db)

    return _audit_to_response(updated_audit)


@router.get("/stats", response_model=AuditStatsResponse)
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


@router.get("/leaderboard", response_model=LeaderboardResponse)
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


@router.get("/recommendations", response_model=RecommendationsResponse)
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


@router.post("/batch", response_model=BatchAuditResponse)
async def trigger_batch_audit(
    request: BatchAuditRequest,
    db: AsyncSession = Depends(get_db),
) -> BatchAuditResponse:
    """Trigger batch audit processing for multiple events.

    Queues events for audit processing based on the provided criteria.
    Events are processed asynchronously.

    Args:
        request: Batch audit request with filtering criteria
        db: Database session

    Returns:
        BatchAuditResponse with number of queued events
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
        return BatchAuditResponse(
            queued_count=0,
            message="No events found matching criteria",
        )

    # Batch load existing audits to avoid N+1 queries
    event_ids = [event.id for event in events]
    audits_result = await db.execute(select(EventAudit).where(EventAudit.event_id.in_(event_ids)))
    audits_by_event_id = {audit.event_id: audit for audit in audits_result.scalars().all()}

    # Get audit service for processing
    service = get_audit_service()
    queued_count = 0

    for event in events:
        # Check if audit exists from batch-loaded map
        audit = audits_by_event_id.get(event.id)

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

        # Run evaluation
        await service.run_full_evaluation(audit, event, db)
        queued_count += 1

    return BatchAuditResponse(
        queued_count=queued_count,
        message=f"Successfully processed {queued_count} events for audit evaluation",
    )
