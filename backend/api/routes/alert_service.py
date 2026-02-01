"""API routes for Alert Service CRUD operations.

Implements NEM-4931: Expose Alert Service CRUD Endpoints.

This module exposes the AlertService for programmatic alert management.
It provides full CRUD operations for alerts, complementing the existing
alert rules endpoints in alerts.py.

Endpoints:
    GET    /api/alert-service/alerts              - List all alerts with pagination
    GET    /api/alert-service/alerts/{alert_id}   - Get a specific alert
    POST   /api/alert-service/alerts              - Create a new alert
    PUT    /api/alert-service/alerts/{alert_id}   - Update an alert
    DELETE /api/alert-service/alerts/{alert_id}   - Delete an alert
    POST   /api/alert-service/alerts/{alert_id}/acknowledge - Acknowledge alert
    POST   /api/alert-service/alerts/{alert_id}/dismiss     - Dismiss alert
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.alert_service import (
    AcknowledgeRequest,
    AlertServiceCreateRequest,
    AlertServiceDeleteResponse,
    AlertServiceListResponse,
    AlertServiceResponse,
    AlertServiceUpdateRequest,
    DismissRequest,
)
from backend.api.schemas.alerts import AlertSeverity as SchemaSeverity
from backend.api.schemas.alerts import AlertStatus as SchemaStatus
from backend.api.schemas.pagination import PaginationMeta
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.models import Alert, AlertSeverity, AlertStatus
from backend.services.alert_service import AlertService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/alert-service", tags=["alert-service"])


def _alert_to_response(alert: Alert) -> dict[str, Any]:
    """Convert an Alert model to response dict."""
    return {
        "id": alert.id,
        "event_id": alert.event_id,
        "rule_id": alert.rule_id,
        "severity": alert.severity.value
        if isinstance(alert.severity, AlertSeverity)
        else alert.severity,
        "status": alert.status.value
        if isinstance(alert.status, AlertStatus)
        else alert.status,
        "dedup_key": alert.dedup_key,
        "channels": alert.channels or [],
        "alert_metadata": alert.alert_metadata,
        "created_at": alert.created_at,
        "updated_at": alert.updated_at,
        "delivered_at": alert.delivered_at,
    }


@router.get(
    "/alerts",
    response_model=AlertServiceListResponse,
    responses={
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def list_alerts(
    status_filter: SchemaStatus | None = Query(
        None, alias="status", description="Filter by alert status"
    ),
    severity_filter: SchemaSeverity | None = Query(
        None, alias="severity", description="Filter by severity level"
    ),
    event_id: int | None = Query(None, description="Filter by event ID"),
    rule_id: str | None = Query(None, description="Filter by rule ID"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: AsyncSession = Depends(get_db),
) -> AlertServiceListResponse:
    """List all alerts with optional filtering and pagination.

    Args:
        status_filter: Filter by alert status (pending, delivered, acknowledged, dismissed)
        severity_filter: Filter by severity level (low, medium, high, critical)
        event_id: Filter by associated event ID
        rule_id: Filter by alert rule ID
        limit: Maximum number of results to return
        offset: Number of results to skip for pagination
        db: Database session

    Returns:
        AlertServiceListResponse with alerts and pagination info
    """
    # Build base query
    query = select(Alert)

    # Apply filters
    if status_filter is not None:
        query = query.where(Alert.status == status_filter.value)
    if severity_filter is not None:
        query = query.where(Alert.severity == severity_filter.value)
    if event_id is not None:
        query = query.where(Alert.event_id == event_id)
    if rule_id is not None:
        query = query.where(Alert.rule_id == rule_id)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Sort by created_at descending (newest first)
    query = query.order_by(Alert.created_at.desc())

    # Apply pagination
    query = query.limit(limit).offset(offset)

    # Execute query
    result = await db.execute(query)
    alerts = result.scalars().all()

    return AlertServiceListResponse(
        items=[AlertServiceResponse(**_alert_to_response(alert)) for alert in alerts],
        pagination=PaginationMeta(
            total=total_count,
            limit=limit,
            offset=offset,
            has_more=total_count > offset + limit,
        ),
    )


@router.get(
    "/alerts/{alert_id}",
    response_model=AlertServiceResponse,
    responses={
        404: {"description": "Alert not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_alert(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
) -> AlertServiceResponse:
    """Get a specific alert by ID.

    Args:
        alert_id: Alert UUID
        db: Database session

    Returns:
        AlertServiceResponse

    Raises:
        HTTPException: 404 if alert not found
    """
    service = AlertService(db)
    alert = await service.get_alert(alert_id)

    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with id {alert_id} not found",
        )

    return AlertServiceResponse(**_alert_to_response(alert))


@router.post(
    "/alerts",
    response_model=AlertServiceResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def create_alert(
    alert_data: AlertServiceCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> AlertServiceResponse:
    """Create a new alert via the Alert Service.

    This endpoint bypasses alert rules and creates an alert directly.
    Useful for programmatic alert creation from external systems.

    Args:
        alert_data: Alert creation data
        db: Database session

    Returns:
        Created AlertServiceResponse
    """
    # Convert schema enums to model enums
    model_severity = AlertSeverity(alert_data.severity.value)
    model_status = AlertStatus(alert_data.status.value)

    service = AlertService(db)
    alert = await service.create_alert(
        event_id=alert_data.event_id,
        severity=model_severity,
        dedup_key=alert_data.dedup_key,
        rule_id=alert_data.rule_id,
        status=model_status,
        channels=alert_data.channels,
        alert_metadata=alert_data.metadata,
    )

    await db.commit()

    logger.info(
        "Created alert %s for event %d via Alert Service",
        alert.id,
        alert.event_id,
    )

    return AlertServiceResponse(**_alert_to_response(alert))


@router.put(
    "/alerts/{alert_id}",
    response_model=AlertServiceResponse,
    responses={
        404: {"description": "Alert not found"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def update_alert(
    alert_id: str,
    alert_data: AlertServiceUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> AlertServiceResponse:
    """Update an existing alert.

    Args:
        alert_id: Alert UUID to update
        alert_data: Update data (only provided fields will be updated)
        db: Database session

    Returns:
        Updated AlertServiceResponse

    Raises:
        HTTPException: 404 if alert not found
    """
    # Convert schema enums to model enums if provided
    model_status = None
    if alert_data.status is not None:
        model_status = AlertStatus(alert_data.status.value)

    model_severity = None
    if alert_data.severity is not None:
        model_severity = AlertSeverity(alert_data.severity.value)

    service = AlertService(db)
    alert = await service.update_alert(
        alert_id,
        status=model_status,
        severity=model_severity,
        channels=alert_data.channels,
        alert_metadata=alert_data.metadata,
    )

    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with id {alert_id} not found",
        )

    await db.commit()

    logger.info("Updated alert %s via Alert Service", alert_id)

    return AlertServiceResponse(**_alert_to_response(alert))


@router.delete(
    "/alerts/{alert_id}",
    response_model=AlertServiceDeleteResponse,
    responses={
        404: {"description": "Alert not found"},
        500: {"description": "Internal server error"},
    },
)
async def delete_alert(
    alert_id: str,
    reason: str | None = Query(None, description="Optional deletion reason"),
    db: AsyncSession = Depends(get_db),
) -> AlertServiceDeleteResponse:
    """Delete an alert.

    Args:
        alert_id: Alert UUID to delete
        reason: Optional reason for deletion
        db: Database session

    Returns:
        AlertServiceDeleteResponse

    Raises:
        HTTPException: 404 if alert not found
    """
    service = AlertService(db)
    deleted = await service.delete_alert(alert_id, reason=reason)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with id {alert_id} not found",
        )

    await db.commit()

    logger.info("Deleted alert %s via Alert Service (reason: %s)", alert_id, reason)

    return AlertServiceDeleteResponse(
        success=True,
        deleted_id=alert_id,
        message=f"Alert {alert_id} deleted successfully",
    )


@router.post(
    "/alerts/{alert_id}/acknowledge",
    response_model=AlertServiceResponse,
    responses={
        404: {"description": "Alert not found"},
        500: {"description": "Internal server error"},
    },
)
async def acknowledge_alert(
    alert_id: str,
    request: AcknowledgeRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> AlertServiceResponse:
    """Acknowledge an alert via the Alert Service.

    Sets the alert status to ACKNOWLEDGED and records the acknowledgment time.

    Args:
        alert_id: Alert UUID to acknowledge
        request: Optional request with correlation_id
        db: Database session

    Returns:
        Updated AlertServiceResponse

    Raises:
        HTTPException: 404 if alert not found
    """
    correlation_id = request.correlation_id if request else None

    service = AlertService(db)
    alert = await service.acknowledge_alert(alert_id, correlation_id=correlation_id)

    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with id {alert_id} not found",
        )

    await db.commit()

    logger.info("Acknowledged alert %s via Alert Service", alert_id)

    return AlertServiceResponse(**_alert_to_response(alert))


@router.post(
    "/alerts/{alert_id}/dismiss",
    response_model=AlertServiceResponse,
    responses={
        404: {"description": "Alert not found"},
        500: {"description": "Internal server error"},
    },
)
async def dismiss_alert(
    alert_id: str,
    request: DismissRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> AlertServiceResponse:
    """Dismiss an alert via the Alert Service.

    Sets the alert status to DISMISSED and optionally records the reason.

    Args:
        alert_id: Alert UUID to dismiss
        request: Optional request with reason and correlation_id
        db: Database session

    Returns:
        Updated AlertServiceResponse

    Raises:
        HTTPException: 404 if alert not found
    """
    reason = request.reason if request else None
    correlation_id = request.correlation_id if request else None

    service = AlertService(db)
    alert = await service.dismiss_alert(
        alert_id, reason=reason, correlation_id=correlation_id
    )

    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with id {alert_id} not found",
        )

    await db.commit()

    logger.info("Dismissed alert %s via Alert Service (reason: %s)", alert_id, reason)

    return AlertServiceResponse(**_alert_to_response(alert))
