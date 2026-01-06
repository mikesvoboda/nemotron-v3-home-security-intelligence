"""API routes for alert rules management.

This module provides CRUD endpoints for managing alert rules, as well as
a test endpoint for validating rule configuration against historical events.

Endpoints:
    GET    /api/alerts/rules              - List all rules
    POST   /api/alerts/rules              - Create rule
    GET    /api/alerts/rules/{rule_id}    - Get rule
    PUT    /api/alerts/rules/{rule_id}    - Update rule
    DELETE /api/alerts/rules/{rule_id}    - Delete rule
    POST   /api/alerts/rules/{rule_id}/test - Test rule against historical events
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.alerts import (
    AlertRuleCreate,
    AlertRuleListResponse,
    AlertRuleResponse,
    AlertRuleUpdate,
    RuleTestEventResult,
    RuleTestRequest,
    RuleTestResponse,
)
from backend.core.database import get_db
from backend.models import AlertRule, Event
from backend.models import AlertSeverity as ModelAlertSeverity
from backend.services.alert_engine import AlertRuleEngine

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


@router.get("", response_model=AlertRuleListResponse)
async def list_rules(
    enabled: bool | None = Query(None, description="Filter by enabled status"),
    severity: str | None = Query(None, description="Filter by severity level"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
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

    return {
        "rules": [_rule_to_response(rule) for rule in rules],
        "count": total_count,
        "limit": limit,
        "offset": offset,
    }


@router.post("", response_model=AlertRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    rule_data: AlertRuleCreate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create a new alert rule.

    Args:
        rule_data: Rule creation data
        db: Database session

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

    return _rule_to_response(rule)


@router.get("/{rule_id}", response_model=AlertRuleResponse)
async def get_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get a specific alert rule by ID.

    Args:
        rule_id: Rule UUID
        db: Database session

    Returns:
        AlertRule

    Raises:
        HTTPException: 404 if rule not found
    """
    result = await db.execute(select(AlertRule).where(AlertRule.id == rule_id))
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert rule with id {rule_id} not found",
        )

    return _rule_to_response(rule)


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
) -> dict[str, Any]:
    """Update an existing alert rule.

    Args:
        rule_id: Rule UUID
        rule_data: Rule update data
        db: Database session

    Returns:
        Updated AlertRule

    Raises:
        HTTPException: 404 if rule not found
    """
    result = await db.execute(select(AlertRule).where(AlertRule.id == rule_id))
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert rule with id {rule_id} not found",
        )

    # Update fields if provided
    update_dict = rule_data.model_dump(exclude_unset=True)
    _apply_rule_updates(rule, rule_data, update_dict)

    await db.commit()
    await db.refresh(rule)

    return _rule_to_response(rule)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an alert rule.

    Args:
        rule_id: Rule UUID
        db: Database session

    Raises:
        HTTPException: 404 if rule not found
    """
    result = await db.execute(select(AlertRule).where(AlertRule.id == rule_id))
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert rule with id {rule_id} not found",
        )

    await db.delete(rule)
    await db.commit()


@router.post("/{rule_id}/test", response_model=RuleTestResponse)
async def test_rule(
    rule_id: str,
    test_data: RuleTestRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Test a rule against historical events.

    This endpoint allows testing rule configuration without actually
    creating alerts. Useful for validating rules before enabling them.

    Args:
        rule_id: Rule UUID
        test_data: Test configuration (event IDs, time override)
        db: Database session

    Returns:
        RuleTestResponse with per-event match results

    Raises:
        HTTPException: 404 if rule not found
    """
    # Get the rule
    result = await db.execute(select(AlertRule).where(AlertRule.id == rule_id))
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert rule with id {rule_id} not found",
        )

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
        return {
            "rule_id": rule.id,
            "rule_name": rule.name,
            "events_tested": 0,
            "events_matched": 0,
            "match_rate": 0.0,
            "results": [],
        }

    # Test the rule against each event
    engine = AlertRuleEngine(db)
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

    return {
        "rule_id": rule.id,
        "rule_name": rule.name,
        "events_tested": events_tested,
        "events_matched": events_matched,
        "match_rate": events_matched / events_tested if events_tested > 0 else 0.0,
        "results": results,
    }
