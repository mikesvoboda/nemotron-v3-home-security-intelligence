"""API routes for alert rules and alert instance management.

This module provides CRUD endpoints for managing alert rules, as well as
a test endpoint for validating rule configuration against historical events.
Also includes endpoints for managing individual alert instances (acknowledge, dismiss).

Alert Rules Endpoints:
    GET    /api/alerts/rules              - List all rules
    POST   /api/alerts/rules              - Create rule
    GET    /api/alerts/rules/{rule_id}    - Get rule
    PUT    /api/alerts/rules/{rule_id}    - Update rule
    DELETE /api/alerts/rules/{rule_id}    - Delete rule
    POST   /api/alerts/rules/{rule_id}/test - Test rule against historical events

Alert Instance Endpoints (NEM-1981):
    POST   /api/alerts/{alert_id}/acknowledge - Acknowledge an alert
    POST   /api/alerts/{alert_id}/dismiss     - Dismiss an alert
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from backend.api.dependencies import (
    get_alert_rule_engine_dep,
    get_alert_rule_or_404,
    get_cache_service_dep,
)
from backend.api.schemas.alerts import (
    AlertResponse,
    AlertRuleCreate,
    AlertRuleListResponse,
    AlertRuleResponse,
    AlertRuleUpdate,
    RuleTestEventResult,
    RuleTestRequest,
    RuleTestResponse,
)
from backend.api.schemas.outbound_webhook import WebhookEventType
from backend.api.schemas.pagination import PaginationMeta
from backend.api.schemas.websocket import WebSocketAlertEventType
from backend.core.constants import CacheInvalidationReason
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.models import Alert, AlertRule, Event
from backend.models import AlertSeverity as ModelAlertSeverity
from backend.models.alert import AlertStatusEnum
from backend.services.alert_engine import AlertRuleEngine
from backend.services.cache_service import CacheService
from backend.services.event_broadcaster import (
    EventBroadcaster,
    broadcast_alert_with_retry_background,
)
from backend.services.webhook_service import (
    trigger_webhook_background,
)

logger = get_logger(__name__)

# Type alias for dependency injection
AlertRuleEngineDep = AlertRuleEngine

router = APIRouter(prefix="/api/alerts/rules", tags=["alert-rules"])


def _rule_to_response(rule: AlertRule) -> dict[str, Any]:
    """Convert an AlertRule model to response dict."""
    return {
        "id": rule.id,
        "name": rule.name,
        "description": rule.description,
        "enabled": rule.enabled,
        "severity": rule.severity.value
        if isinstance(rule.severity, ModelAlertSeverity)
        else rule.severity,
        "risk_threshold": rule.risk_threshold,
        "object_types": rule.object_types,
        "camera_ids": rule.camera_ids,
        "zone_ids": rule.zone_ids,
        "min_confidence": rule.min_confidence,
        "schedule": rule.schedule,
        "conditions": rule.conditions,
        "dedup_key_template": rule.dedup_key_template,
        "cooldown_seconds": rule.cooldown_seconds,
        "channels": rule.channels or [],
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
    }


@router.get(
    "",
    response_model=AlertRuleListResponse,
    responses={
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def list_rules(
    enabled: bool | None = Query(None, description="Filter by enabled status"),
    severity: str | None = Query(None, description="Filter by severity level"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: AsyncSession = Depends(get_db),
) -> AlertRuleListResponse:
    """List all alert rules with optional filtering and pagination.

    Args:
        enabled: Filter by enabled status
        severity: Filter by severity level (low, medium, high, critical)
        limit: Maximum number of results to return
        offset: Number of results to skip for pagination
        db: Database session

    Returns:
        AlertRuleListResponse with rules and pagination info
    """
    # Build base query
    query = select(AlertRule)

    # Apply filters
    if enabled is not None:
        query = query.where(AlertRule.enabled == enabled)
    if severity:
        query = query.where(AlertRule.severity == severity)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Sort by name
    query = query.order_by(AlertRule.name)

    # Apply pagination
    query = query.limit(limit).offset(offset)

    # Execute query
    result = await db.execute(query)
    rules = result.scalars().all()

    return AlertRuleListResponse(
        items=[AlertRuleResponse(**_rule_to_response(rule)) for rule in rules],
        pagination=PaginationMeta(
            total=total_count,
            limit=limit,
            offset=offset,
            has_more=total_count > offset + limit,
        ),
    )


@router.post(
    "",
    response_model=AlertRuleResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def create_rule(
    rule_data: AlertRuleCreate,
    db: AsyncSession = Depends(get_db),
    cache: CacheService = Depends(get_cache_service_dep),
) -> AlertRuleResponse:
    """Create a new alert rule.

    Args:
        rule_data: Rule creation data
        db: Database session
        cache: Cache service for cache invalidation (NEM-1952)

    Returns:
        Created AlertRule
    """
    # Convert severity from schema enum to model enum
    model_severity = ModelAlertSeverity(rule_data.severity.value)

    # Convert schedule to dict if it's a Pydantic model
    schedule = None
    if rule_data.schedule:
        schedule = rule_data.schedule.model_dump(exclude_none=True)

    # Convert legacy conditions to dict if provided
    conditions = None
    if rule_data.conditions:
        conditions = rule_data.conditions.model_dump(exclude_none=True)

    rule = AlertRule(
        name=rule_data.name,
        description=rule_data.description,
        enabled=rule_data.enabled,
        severity=model_severity,
        risk_threshold=rule_data.risk_threshold,
        object_types=rule_data.object_types,
        camera_ids=rule_data.camera_ids,
        zone_ids=rule_data.zone_ids,
        min_confidence=rule_data.min_confidence,
        schedule=schedule,
        conditions=conditions,
        dedup_key_template=rule_data.dedup_key_template,
        cooldown_seconds=rule_data.cooldown_seconds,
        channels=rule_data.channels,
    )

    db.add(rule)
    await db.commit()
    await db.refresh(rule)

    # Invalidate alert-related caches after successful create (NEM-1952)
    try:
        await cache.invalidate_alerts(reason=CacheInvalidationReason.ALERT_RULE_CREATED)
    except Exception as e:
        # Cache invalidation is non-critical - log but don't fail the request
        logger.warning(f"Cache invalidation failed after alert rule create: {e}")

    return AlertRuleResponse(**_rule_to_response(rule))


@router.get(
    "/{rule_id}",
    response_model=AlertRuleResponse,
    response_model_exclude_unset=True,
    responses={
        404: {"description": "Alert rule not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
) -> AlertRuleResponse:
    """Get a specific alert rule by ID.

    Args:
        rule_id: Rule UUID
        db: Database session

    Returns:
        AlertRule

    Raises:
        HTTPException: 404 if rule not found
    """
    rule = await get_alert_rule_or_404(rule_id, db)
    return AlertRuleResponse(**_rule_to_response(rule))


def _apply_rule_updates(rule: AlertRule, rule_data: AlertRuleUpdate, update_dict: dict) -> None:
    """Apply update fields to rule model.

    Extracted to reduce branching in update_rule endpoint.
    """
    # Direct field mappings (simple assignment)
    simple_fields = [
        "name",
        "description",
        "enabled",
        "risk_threshold",
        "object_types",
        "camera_ids",
        "zone_ids",
        "min_confidence",
        "channels",
    ]
    for field in simple_fields:
        if field in update_dict:
            setattr(rule, field, getattr(rule_data, field))

    # Fields that need None check before assignment
    if "severity" in update_dict and rule_data.severity is not None:
        # Convert schema enum to model enum
        rule.severity = ModelAlertSeverity(rule_data.severity.value)
    if "dedup_key_template" in update_dict and rule_data.dedup_key_template is not None:
        rule.dedup_key_template = rule_data.dedup_key_template
    if "cooldown_seconds" in update_dict and rule_data.cooldown_seconds is not None:
        rule.cooldown_seconds = rule_data.cooldown_seconds

    # Pydantic model fields that need conversion
    if "schedule" in update_dict:
        rule.schedule = (
            rule_data.schedule.model_dump(exclude_none=True) if rule_data.schedule else None
        )
    if "conditions" in update_dict:
        rule.conditions = (
            rule_data.conditions.model_dump(exclude_none=True) if rule_data.conditions else None
        )


@router.put("/{rule_id}", response_model=AlertRuleResponse)
async def update_rule(
    rule_id: str,
    rule_data: AlertRuleUpdate,
    db: AsyncSession = Depends(get_db),
    cache: CacheService = Depends(get_cache_service_dep),
) -> AlertRuleResponse:
    """Update an existing alert rule.

    Args:
        rule_id: Rule UUID
        rule_data: Rule update data
        db: Database session
        cache: Cache service for cache invalidation (NEM-1952)

    Returns:
        Updated AlertRule

    Raises:
        HTTPException: 404 if rule not found
    """
    rule = await get_alert_rule_or_404(rule_id, db)

    # Update fields if provided
    update_dict = rule_data.model_dump(exclude_unset=True)
    _apply_rule_updates(rule, rule_data, update_dict)

    await db.commit()
    await db.refresh(rule)

    # Invalidate alert-related caches after successful update (NEM-1952)
    try:
        await cache.invalidate_alerts(reason=CacheInvalidationReason.ALERT_RULE_UPDATED)
    except Exception as e:
        # Cache invalidation is non-critical - log but don't fail the request
        logger.warning(f"Cache invalidation failed after alert rule update: {e}")

    return AlertRuleResponse(**_rule_to_response(rule))


@router.delete(
    "/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"description": "Alert rule not found"},
        500: {"description": "Internal server error"},
    },
)
async def delete_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    cache: CacheService = Depends(get_cache_service_dep),
) -> None:
    """Delete an alert rule.

    Args:
        rule_id: Rule UUID
        db: Database session
        cache: Cache service for cache invalidation (NEM-1952)

    Raises:
        HTTPException: 404 if rule not found
    """
    rule = await get_alert_rule_or_404(rule_id, db)
    await db.delete(rule)
    await db.commit()

    # Invalidate alert-related caches after successful delete (NEM-1952)
    try:
        await cache.invalidate_alerts(reason=CacheInvalidationReason.ALERT_RULE_DELETED)
    except Exception as e:
        # Cache invalidation is non-critical - log but don't fail the request
        logger.warning(f"Cache invalidation failed after alert rule delete: {e}")


@router.post(
    "/{rule_id}/test",
    response_model=RuleTestResponse,
    responses={
        404: {"description": "Alert rule not found"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def test_rule(
    rule_id: str,
    test_data: RuleTestRequest,
    db: AsyncSession = Depends(get_db),
    engine: AlertRuleEngineDep = Depends(get_alert_rule_engine_dep),
) -> RuleTestResponse:
    """Test a rule against historical events.

    This endpoint allows testing rule configuration without actually
    creating alerts. Useful for validating rules before enabling them.

    Args:
        rule_id: Rule UUID
        test_data: Test configuration (event IDs, time override)
        db: Database session
        engine: AlertRuleEngine injected via Depends()

    Returns:
        RuleTestResponse with per-event match results

    Raises:
        HTTPException: 404 if rule not found
    """
    rule = await get_alert_rule_or_404(rule_id, db)

    # Get events to test against
    if test_data.event_ids:
        # Test against specific events
        events_query = select(Event).where(Event.id.in_(test_data.event_ids))
    else:
        # Test against recent events
        events_query = select(Event).order_by(Event.started_at.desc()).limit(test_data.limit)

    events_result = await db.execute(events_query)
    events = list(events_result.scalars().all())

    if not events:
        return RuleTestResponse(
            rule_id=rule.id,
            rule_name=rule.name,
            events_tested=0,
            events_matched=0,
            match_rate=0.0,
            results=[],
        )

    # Test the rule against each event (engine injected via DI)
    test_time = test_data.test_time or datetime.now(UTC)

    test_results = await engine.test_rule_against_events(rule, events, test_time)

    # Build response
    results = [
        RuleTestEventResult(
            event_id=r["event_id"],
            camera_id=r["camera_id"],
            risk_score=r["risk_score"],
            object_types=r["object_types"],
            matches=r["matches"],
            matched_conditions=r["matched_conditions"],
            started_at=r["started_at"],
        )
        for r in test_results
    ]

    events_matched = sum(1 for r in results if r.matches)
    events_tested = len(results)

    return RuleTestResponse(
        rule_id=rule.id,
        rule_name=rule.name,
        events_tested=events_tested,
        events_matched=events_matched,
        match_rate=events_matched / events_tested if events_tested > 0 else 0.0,
        results=results,
    )


# =============================================================================
# Alert Instance Endpoints (NEM-1981)
# =============================================================================

alerts_instance_router = APIRouter(prefix="/api/alerts", tags=["alerts"])


# Legacy aliases for backward compatibility with existing tests
# These delegate to the unified Alert.to_dict() method on the model
def _alert_to_response_dict(alert: Alert) -> dict[str, Any]:
    """Convert an Alert model to response dict.

    Deprecated: Use alert.to_dict() directly instead.
    Kept for backward compatibility with existing tests.
    """
    return alert.to_dict(for_websocket=False)


def _alert_to_websocket_data(alert: Alert) -> dict[str, Any]:
    """Convert an Alert model to WebSocket broadcast data.

    Deprecated: Use alert.to_dict(for_websocket=True) directly instead.
    Kept for backward compatibility with existing tests.
    """
    return alert.to_dict(for_websocket=True)


def _build_alert_webhook_data(alert: Alert) -> dict[str, Any]:
    """Build webhook payload data for an alert (NEM-3624).

    Args:
        alert: Alert instance.

    Returns:
        Dictionary with alert data for webhook payload.
    """
    return {
        "alert_id": alert.id,
        "event_id": alert.event_id,
        "rule_id": alert.rule_id,
        "severity": alert.severity.value if hasattr(alert.severity, "value") else alert.severity,
        "status": alert.status.value if hasattr(alert.status, "value") else alert.status,
        "dedup_key": alert.dedup_key,
        "channels": alert.channels or [],
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
    }


async def _get_alert_or_404(alert_id: str, db: AsyncSession) -> Alert:
    """Get an alert by ID or raise 404."""
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return alert


@alerts_instance_router.post(
    "/{alert_id}/acknowledge",
    response_model=AlertResponse,
    responses={
        404: {"description": "Alert not found"},
        409: {
            "description": "Alert cannot be acknowledged (wrong status or concurrent modification)"
        },
        500: {"description": "Internal server error"},
    },
)
async def acknowledge_alert(
    alert_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> AlertResponse:
    """Acknowledge an alert.

    Marks an alert as acknowledged and broadcasts the state change via WebSocket.
    Only alerts with status PENDING or DELIVERED can be acknowledged.

    Uses optimistic locking to prevent race conditions when multiple requests
    attempt to modify the same alert concurrently. If a concurrent modification
    is detected, returns HTTP 409 Conflict.

    NEM-2582: WebSocket broadcast now uses background task with retry logic
    to ensure delivery without blocking the main request.

    Args:
        alert_id: Alert UUID
        background_tasks: FastAPI background tasks for non-blocking broadcast
        db: Database session

    Returns:
        Updated AlertResponse

    Raises:
        HTTPException: 404 if alert not found, 409 if alert cannot be acknowledged
                      or if concurrent modification detected
    """
    alert = await _get_alert_or_404(alert_id, db)

    # Check if alert can be acknowledged
    if alert.status not in (AlertStatusEnum.PENDING, AlertStatusEnum.DELIVERED):
        raise HTTPException(
            status_code=409,
            detail=f"Alert cannot be acknowledged. Current status: {alert.status.value}",
        )

    # Update alert status with optimistic locking (NEM-2581)
    alert.status = AlertStatusEnum.ACKNOWLEDGED
    try:
        await db.commit()
    except StaleDataError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Alert was modified by another request. Please refresh and retry.",
        ) from None
    await db.refresh(alert)

    # Broadcast WebSocket event with retry in background (NEM-2582)
    # This ensures the main request returns immediately while broadcast retries continue
    try:
        broadcaster = EventBroadcaster.get_instance()
        alert_data = _alert_to_websocket_data(alert)
        background_tasks.add_task(
            broadcast_alert_with_retry_background,
            broadcaster,
            alert_data,
            WebSocketAlertEventType.ALERT_ACKNOWLEDGED,
            max_retries=3,
            metrics=broadcaster.broadcast_metrics,
        )
    except RuntimeError as e:
        # Log if broadcaster not initialized, but don't fail the request
        logger.warning(f"Failed to schedule alert broadcast: {e}")

    # Trigger outbound webhooks for ALERT_ACKNOWLEDGED event (NEM-3624)
    # Uses background task to avoid blocking the main request
    background_tasks.add_task(
        trigger_webhook_background,
        db,
        WebhookEventType.ALERT_ACKNOWLEDGED,
        _build_alert_webhook_data(alert),
        alert.id,
    )

    return AlertResponse(**alert.to_dict())


@alerts_instance_router.post(
    "/{alert_id}/dismiss",
    response_model=AlertResponse,
    responses={
        404: {"description": "Alert not found"},
        409: {"description": "Alert cannot be dismissed (wrong status or concurrent modification)"},
        500: {"description": "Internal server error"},
    },
)
async def dismiss_alert(
    alert_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> AlertResponse:
    """Dismiss an alert.

    Marks an alert as dismissed and broadcasts the state change via WebSocket.
    Only alerts with status PENDING, DELIVERED, or ACKNOWLEDGED can be dismissed.

    Uses optimistic locking to prevent race conditions when multiple requests
    attempt to modify the same alert concurrently. If a concurrent modification
    is detected, returns HTTP 409 Conflict.

    NEM-2582: WebSocket broadcast now uses background task with retry logic
    to ensure delivery without blocking the main request.

    Args:
        alert_id: Alert UUID
        background_tasks: FastAPI background tasks for non-blocking broadcast
        db: Database session

    Returns:
        Updated AlertResponse

    Raises:
        HTTPException: 404 if alert not found, 409 if alert cannot be dismissed
                      or if concurrent modification detected
    """
    alert = await _get_alert_or_404(alert_id, db)

    # Check if alert can be dismissed (only DISMISSED alerts cannot be dismissed again)
    if alert.status == AlertStatusEnum.DISMISSED:
        raise HTTPException(
            status_code=409,
            detail="Alert is already dismissed",
        )

    # Update alert status with optimistic locking (NEM-2581)
    alert.status = AlertStatusEnum.DISMISSED
    try:
        await db.commit()
    except StaleDataError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Alert was modified by another request. Please refresh and retry.",
        ) from None
    await db.refresh(alert)

    # Broadcast WebSocket event with retry in background (NEM-2582)
    # This ensures the main request returns immediately while broadcast retries continue
    try:
        broadcaster = EventBroadcaster.get_instance()
        alert_data = _alert_to_websocket_data(alert)
        background_tasks.add_task(
            broadcast_alert_with_retry_background,
            broadcaster,
            alert_data,
            WebSocketAlertEventType.ALERT_DISMISSED,
            max_retries=3,
            metrics=broadcaster.broadcast_metrics,
        )
    except RuntimeError as e:
        # Log if broadcaster not initialized, but don't fail the request
        logger.warning(f"Failed to schedule alert broadcast: {e}")

    # Trigger outbound webhooks for ALERT_DISMISSED event (NEM-3624)
    # Uses background task to avoid blocking the main request
    background_tasks.add_task(
        trigger_webhook_background,
        db,
        WebhookEventType.ALERT_DISMISSED,
        _build_alert_webhook_data(alert),
        alert.id,
    )

    return AlertResponse(**alert.to_dict())
