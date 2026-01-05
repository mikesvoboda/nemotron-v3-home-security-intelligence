"""API routes for AI pipeline audit management.

This module provides endpoints for auditing AI pipeline performance,
including model contributions, quality scores, and recommendations.
It also includes the Prompt Playground API for managing AI model configurations.
"""

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.ai_audit import (
    AllPromptsResponse,
    AuditStatsResponse,
    BatchAuditRequest,
    BatchAuditResponse,
    CustomTestPromptRequest,
    CustomTestPromptResponse,
    EventAuditResponse,
    LeaderboardResponse,
    ModelContributions,
    ModelLeaderboardEntry,
    ModelPromptResponse,
    PromptConfigRequest,
    PromptConfigResponse,
    PromptExportResponse,
    PromptHistoryEntry,
    PromptHistoryResponse,
    PromptImportRequest,
    PromptImportResponse,
    PromptImprovements,
    PromptRestoreRequest,
    PromptRestoreResponse,
    PromptTestRequest,
    PromptTestResponse,
    PromptTestResultAfter,
    PromptTestResultBefore,
    PromptUpdateRequest,
    PromptUpdateResponse,
    QualityScores,
    RecommendationItem,
    RecommendationsResponse,
)
from backend.core.database import get_db
from backend.models.audit import AuditAction
from backend.models.event import Event
from backend.models.event_audit import EventAudit
from backend.models.prompt_config import PromptConfig
from backend.services.audit import AuditService
from backend.services.audit_service import get_audit_service
from backend.services.prompt_storage import SUPPORTED_MODELS, get_prompt_storage

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

    # Log the audit entry for AI re-evaluation
    await AuditService.log_action(
        db=db,
        action=AuditAction.AI_REEVALUATED,
        resource_type="event",
        resource_id=str(event_id),
        actor="anonymous",
        details={
            "is_force": force,
            "overall_quality_score": updated_audit.overall_quality_score,
        },
        request=request,
    )
    await db.commit()

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


# =============================================================================
# Prompt Playground Endpoints
# =============================================================================


def _validate_model_name(model: str) -> None:
    """Validate that a model name is supported.

    Args:
        model: Model name to validate

    Raises:
        HTTPException: 404 if model is not supported
    """
    if model not in SUPPORTED_MODELS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model}' not found. Supported models: {sorted(SUPPORTED_MODELS)}",
        )


@router.get("/prompts", response_model=AllPromptsResponse)
async def get_all_prompts() -> AllPromptsResponse:
    """Get current prompt configurations for all AI models.

    Returns configurations for nemotron, florence2, yolo_world, xclip,
    and fashion_clip models with their current versions.

    Returns:
        AllPromptsResponse containing all model configurations
    """
    storage = get_prompt_storage()
    all_configs = storage.get_all_configs()

    prompts = {}
    for model_name, data in all_configs.items():
        prompts[model_name] = ModelPromptResponse(
            model_name=model_name,
            config=data.get("config", {}),
            version=data.get("version", 1),
            updated_at=datetime.fromisoformat(
                data.get("updated_at", datetime.now(UTC).isoformat())
            ),
        )

    return AllPromptsResponse(prompts=prompts)


# NOTE: Static routes must be defined BEFORE dynamic routes like /prompts/{model}
# to prevent FastAPI from matching "history", "export", "test" as model names.


@router.post("/test-prompt", response_model=CustomTestPromptResponse)
async def test_custom_prompt(
    request: CustomTestPromptRequest,
    db: AsyncSession = Depends(get_db),
) -> CustomTestPromptResponse:
    """Test a custom prompt against an existing event for A/B testing.

    This endpoint allows testing a custom prompt without persisting results.
    It's designed for the Prompt Playground A/B testing feature where users
    can experiment with different prompts and compare results.

    The endpoint:
    1. Fetches the event with its detections
    2. Builds context from the event data
    3. Calls the AI model with the custom prompt (or mocks if service unavailable)
    4. Returns results WITHOUT saving to database

    Args:
        request: Test request containing event_id, custom_prompt, and optional
                 parameters (temperature, max_tokens, model)
        db: Database session

    Returns:
        CustomTestPromptResponse with risk analysis results

    Raises:
        HTTPException: 404 if event not found
        HTTPException: 400 if prompt is invalid (empty or too long)
        HTTPException: 503 if AI service is unavailable
        HTTPException: 408 if request times out (>60s)
    """
    import time

    # Validate prompt is not empty (Pydantic handles min_length but double-check)
    if not request.custom_prompt or not request.custom_prompt.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Custom prompt cannot be empty",
        )

    # Validate prompt length (arbitrary max of 50000 chars to prevent abuse)
    if len(request.custom_prompt) > 50000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Custom prompt exceeds maximum length of 50000 characters",
        )

    # Fetch the event
    event_result = await db.execute(select(Event).where(Event.id == request.event_id))
    event = event_result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {request.event_id} not found",
        )

    # Record start time for processing_time_ms
    start_time = time.perf_counter()

    # Build context from event data
    # In a real implementation, this would:
    # 1. Fetch associated detections
    # 2. Build enriched context
    # 3. Call the actual Nemotron service
    # For now, we return mock results based on event data

    # Mock implementation - in production this would call the actual AI service
    # The mock provides deterministic results based on event data for testing
    mock_risk_score = event.risk_score if event.risk_score is not None else 50
    mock_risk_level = _get_risk_level(mock_risk_score)

    # Calculate processing time
    processing_time_ms = int((time.perf_counter() - start_time) * 1000)

    # Estimate tokens used (rough approximation: ~4 chars per token)
    tokens_used = len(request.custom_prompt) // 4 + 100  # +100 for response overhead

    return CustomTestPromptResponse(
        risk_score=mock_risk_score,
        risk_level=mock_risk_level,
        reasoning=event.reasoning or "No reasoning available for this event.",
        summary=event.summary or "Event analysis summary not available.",
        entities=[],  # Would be populated from actual analysis
        flags=[],  # Would be populated from actual analysis
        recommended_action=_get_recommended_action(mock_risk_level),
        processing_time_ms=processing_time_ms,
        tokens_used=tokens_used,
    )


def _get_risk_level(risk_score: int) -> str:
    """Map risk score to risk level.

    Args:
        risk_score: Integer risk score from 0-100

    Returns:
        Risk level string: low, medium, high, or critical
    """
    if risk_score < 25:
        return "low"
    elif risk_score < 50:
        return "medium"
    elif risk_score < 75:
        return "high"
    else:
        return "critical"


def _get_recommended_action(risk_level: str) -> str:
    """Get recommended action based on risk level.

    Args:
        risk_level: Risk level string

    Returns:
        Recommended action string
    """
    actions = {
        "low": "Monitor - No immediate action required",
        "medium": "Review - Check event details when convenient",
        "high": "Investigate - Review event details promptly",
        "critical": "Alert - Immediate attention required",
    }
    return actions.get(risk_level, "Review event details")


@router.post("/prompts/test", response_model=PromptTestResponse)
async def test_prompt(
    request: PromptTestRequest,
    db: AsyncSession = Depends(get_db),
) -> PromptTestResponse:
    """Test a modified prompt configuration against a specific event.

    Runs inference with both the current and modified configurations,
    returning a comparison of the results to help evaluate changes.

    Note: This currently returns mock results. In production, it would
    call the actual AI services with the modified configuration.

    Args:
        request: Test request with model name, config, and event ID
        db: Database session

    Returns:
        PromptTestResponse with before/after comparison

    Raises:
        HTTPException: 404 if model or event not found, 400 if config invalid
    """
    _validate_model_name(request.model)

    # Verify the event exists
    event_result = await db.execute(select(Event).where(Event.id == request.event_id))
    event = event_result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {request.event_id} not found",
        )

    storage = get_prompt_storage()

    # Run mock test
    try:
        results = storage.run_mock_test(
            model_name=request.model,
            config=request.config,
            event_id=request.event_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    return PromptTestResponse(
        before=PromptTestResultBefore(
            score=results["before"]["score"],
            risk_level=results["before"]["risk_level"],
            summary=results["before"]["summary"],
        ),
        after=PromptTestResultAfter(
            score=results["after"]["score"],
            risk_level=results["after"]["risk_level"],
            summary=results["after"]["summary"],
        ),
        improved=results["improved"],
        inference_time_ms=results["inference_time_ms"],
    )


@router.get("/prompts/history", response_model=dict[str, PromptHistoryResponse])
async def get_all_prompts_history(
    limit: int = Query(10, ge=1, le=100, description="Max versions per model"),
) -> dict[str, PromptHistoryResponse]:
    """Get version history for all AI models.

    Returns the most recent versions for each supported model.

    Args:
        limit: Maximum number of versions to return per model (1-100, default 10)

    Returns:
        Dict mapping model names to their version histories
    """
    storage = get_prompt_storage()
    result = {}

    for model_name in sorted(SUPPORTED_MODELS):
        versions = storage.get_history(model_name, limit=limit)
        total = storage.get_total_versions(model_name)

        result[model_name] = PromptHistoryResponse(
            model_name=model_name,
            versions=[
                PromptHistoryEntry(
                    version=v.version,
                    config=v.config,
                    created_at=v.created_at,
                    created_by=v.created_by,
                    description=v.description,
                )
                for v in versions
            ],
            total_versions=total,
        )

    return result


@router.get("/prompts/export", response_model=PromptExportResponse)
async def export_prompts() -> PromptExportResponse:
    """Export all AI model configurations as JSON.

    Returns all current configurations in a format suitable for
    backup or transfer to another instance.

    Returns:
        PromptExportResponse with all configurations
    """
    storage = get_prompt_storage()
    export_data = storage.export_all()

    return PromptExportResponse(
        exported_at=datetime.fromisoformat(export_data["exported_at"]),
        version=export_data["version"],
        prompts=export_data["prompts"],
    )


@router.post("/prompts/import", response_model=PromptImportResponse)
async def import_prompts(request: PromptImportRequest) -> PromptImportResponse:
    """Import AI model configurations from JSON.

    Imports configurations for multiple models at once. By default,
    existing configurations are not overwritten unless overwrite=true.

    Args:
        request: Import request with configurations and overwrite flag

    Returns:
        PromptImportResponse with import results

    Raises:
        HTTPException: 400 if no prompts provided for import
    """
    if not request.prompts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No prompts provided for import. Request body must contain at least one model configuration.",
        )

    storage = get_prompt_storage()

    # Validate all configurations first
    errors: list[str] = []
    for model_name, config in request.prompts.items():
        if model_name not in SUPPORTED_MODELS:
            errors.append(f"{model_name}: Unsupported model")
            continue

        validation_errors = storage.validate_config(model_name, config)
        if validation_errors:
            errors.append(f"{model_name}: {'; '.join(validation_errors)}")

    # If there are validation errors and we're overwriting, fail early
    if errors and request.overwrite:
        return PromptImportResponse(
            imported_count=0,
            skipped_count=0,
            errors=errors,
            message="Import failed due to validation errors",
        )

    # Perform the import
    results = storage.import_configs(
        configs=request.prompts,
        overwrite=request.overwrite,
        created_by="import",
    )

    imported_models = results["imported"].split(", ") if results["imported"] != "none" else []
    skipped_models = results["skipped"].split(", ") if results["skipped"] != "none" else []
    error_list = results["errors"].split("; ") if results["errors"] != "none" else []

    # Combine validation errors with import errors
    all_errors = errors + error_list if error_list != ["none"] else errors

    imported_count = len(imported_models) if imported_models != ["none"] else 0
    skipped_count = len(skipped_models) if skipped_models != ["none"] else 0

    message = f"Imported {imported_count} model(s)"
    if skipped_count > 0:
        message += f", skipped {skipped_count} (already exist)"
    if all_errors:
        message += f", {len(all_errors)} error(s)"

    return PromptImportResponse(
        imported_count=imported_count,
        skipped_count=skipped_count,
        errors=all_errors,
        message=message,
    )


# Dynamic routes with path parameters must come AFTER static routes


@router.get("/prompts/{model}", response_model=ModelPromptResponse)
async def get_model_prompt(model: str) -> ModelPromptResponse:
    """Get current prompt configuration for a specific AI model.

    Args:
        model: Model name (nemotron, florence2, yolo_world, xclip, fashion_clip)

    Returns:
        ModelPromptResponse with current configuration

    Raises:
        HTTPException: 404 if model not found
    """
    _validate_model_name(model)

    storage = get_prompt_storage()
    data = storage.get_config_with_metadata(model)

    return ModelPromptResponse(
        model_name=model,
        config=data.get("config", {}),
        version=data.get("version", 1),
        updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(UTC).isoformat())),
    )


@router.put("/prompts/{model}", response_model=PromptUpdateResponse)
async def update_model_prompt(
    model: str,
    request: PromptUpdateRequest,
) -> PromptUpdateResponse:
    """Update prompt configuration for a specific AI model.

    Creates a new version of the configuration with the provided changes.
    The previous version is preserved in history.

    Args:
        model: Model name to update
        request: New configuration and optional description

    Returns:
        PromptUpdateResponse with new version info

    Raises:
        HTTPException: 404 if model not found, 400 if configuration invalid
    """
    _validate_model_name(model)

    storage = get_prompt_storage()

    # Validate the configuration
    validation_errors = storage.validate_config(model, request.config)
    if validation_errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid configuration: {'; '.join(validation_errors)}",
        )

    # Update the configuration
    version = storage.update_config(
        model_name=model,
        config=request.config,
        created_by="user",
        description=request.description,
    )

    return PromptUpdateResponse(
        model_name=model,
        version=version.version,
        message=f"Configuration updated to version {version.version}",
        config=version.config,
    )


@router.get("/prompts/history/{model}", response_model=PromptHistoryResponse)
async def get_model_history(
    model: str,
    limit: int = Query(50, ge=1, le=100, description="Max versions to return"),
    offset: int = Query(0, ge=0, description="Number of versions to skip"),
) -> PromptHistoryResponse:
    """Get version history for a specific AI model.

    Returns all versions of the model's configuration, newest first,
    with pagination support.

    Args:
        model: Model name to get history for
        limit: Maximum versions to return (1-100, default 50)
        offset: Number of versions to skip (default 0)

    Returns:
        PromptHistoryResponse with version list

    Raises:
        HTTPException: 404 if model not found
    """
    _validate_model_name(model)

    storage = get_prompt_storage()
    versions = storage.get_history(model, limit=limit, offset=offset)
    total = storage.get_total_versions(model)

    return PromptHistoryResponse(
        model_name=model,
        versions=[
            PromptHistoryEntry(
                version=v.version,
                config=v.config,
                created_at=v.created_at,
                created_by=v.created_by,
                description=v.description,
            )
            for v in versions
        ],
        total_versions=total,
    )


@router.post("/prompts/history/{version}", response_model=PromptRestoreResponse)
async def restore_prompt_version(
    version: int,
    model: str = Query(..., description="Model name to restore version for"),
    request: PromptRestoreRequest | None = None,
) -> PromptRestoreResponse:
    """Restore a specific version of a model's prompt configuration.

    Creates a new version with the configuration from the specified version.
    The restore action is recorded in the version history.

    Args:
        version: Version number to restore
        model: Model name to restore version for
        request: Optional restore request with description

    Returns:
        PromptRestoreResponse with restore details

    Raises:
        HTTPException: 404 if model or version not found
    """
    _validate_model_name(model)

    storage = get_prompt_storage()

    # Check if version exists
    old_version = storage.get_version(model, version)
    if old_version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version} not found for model {model}",
        )

    # Restore the version
    description = request.description if request else None
    new_version = storage.restore_version(
        model_name=model,
        version=version,
        created_by="user",
        description=description,
    )

    return PromptRestoreResponse(
        model_name=model,
        restored_version=version,
        new_version=new_version.version,
        message=f"Restored version {version} as new version {new_version.version}",
    )


# =============================================================================
# Database-backed Prompt Config Endpoints (for Playground Save functionality)
# =============================================================================

# Supported model names for database-backed prompt configs
# Note: Uses hyphen-separated names as specified in API spec
DB_SUPPORTED_MODELS = frozenset({"nemotron", "florence-2", "yolo-world", "x-clip", "fashion-clip"})


def _validate_db_model_name(model: str) -> None:
    """Validate that a model name is supported for database-backed configs.

    Args:
        model: Model name to validate

    Raises:
        HTTPException: 404 if model is not supported
    """
    if model not in DB_SUPPORTED_MODELS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model}' not found. Supported models: {sorted(DB_SUPPORTED_MODELS)}",
        )


@router.get("/prompt-config/{model}", response_model=PromptConfigResponse)
async def get_prompt_config(
    model: str,
    db: AsyncSession = Depends(get_db),
) -> PromptConfigResponse:
    """Get current prompt configuration for a model (database-backed).

    Retrieves the prompt configuration from the database for the specified model.
    Returns 404 if no configuration exists for the model.

    Args:
        model: Model name (nemotron, florence-2, yolo-world, x-clip, fashion-clip)
        db: Database session

    Returns:
        PromptConfigResponse with current configuration

    Raises:
        HTTPException: 404 if model not found or no configuration exists
    """
    _validate_db_model_name(model)

    result = await db.execute(select(PromptConfig).where(PromptConfig.model == model))
    config = result.scalar_one_or_none()

    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No configuration found for model '{model}'",
        )

    return PromptConfigResponse(
        model=config.model,
        system_prompt=config.system_prompt,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        version=config.version,
        updated_at=config.updated_at,
    )


@router.put("/prompt-config/{model}", response_model=PromptConfigResponse)
async def update_prompt_config(
    model: str,
    request: PromptConfigRequest,
    db: AsyncSession = Depends(get_db),
) -> PromptConfigResponse:
    """Update prompt configuration for a model (database-backed).

    Creates or updates the prompt configuration in the database.
    If updating an existing config, increments the version number.

    Args:
        model: Model name (nemotron, florence-2, yolo-world, x-clip, fashion-clip)
        request: New configuration with system_prompt, temperature, max_tokens
        db: Database session

    Returns:
        PromptConfigResponse with updated configuration

    Raises:
        HTTPException: 404 if model not found, 400 if configuration invalid
    """
    _validate_db_model_name(model)

    # Check if config exists
    result = await db.execute(select(PromptConfig).where(PromptConfig.model == model))
    config = result.scalar_one_or_none()

    if config is None:
        # Create new config
        config = PromptConfig(
            model=model,
            system_prompt=request.system_prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            version=1,
        )
        db.add(config)
    else:
        # Update existing config
        config.system_prompt = request.system_prompt
        config.temperature = request.temperature
        config.max_tokens = request.max_tokens
        config.version += 1
        config.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(config)

    return PromptConfigResponse(
        model=config.model,
        system_prompt=config.system_prompt,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        version=config.version,
        updated_at=config.updated_at,
    )
