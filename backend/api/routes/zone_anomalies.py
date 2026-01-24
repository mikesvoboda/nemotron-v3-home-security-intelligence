"""API routes for zone anomaly detection and management.

This module provides endpoints for querying and managing zone anomalies,
which are detected when real-time activity deviates from established baselines.

Endpoints:
    GET /api/zones/anomalies - List all anomalies across all zones
    GET /api/zones/{zone_id}/anomalies - List anomalies for a specific zone
    POST /api/zones/anomalies/{anomaly_id}/acknowledge - Acknowledge an anomaly

Related: NEM-3199 (Frontend Anomaly Alert Integration)
Related: NEM-3198 (Backend Anomaly Detection Service)
Related: NEM-3495 (Zone Anomalies widget error)
"""

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.pagination import PaginationMeta
from backend.api.schemas.zone_anomaly import (
    ZoneAnomalyAcknowledgeResponse,
    ZoneAnomalyListResponse,
)
from backend.core.database import get_db
from backend.core.time_utils import utc_now
from backend.models.zone_anomaly import ZoneAnomaly

router = APIRouter(prefix="/api/zones", tags=["zone-anomalies"])


@router.get("/anomalies", response_model=ZoneAnomalyListResponse)
async def list_all_anomalies(
    severity: Annotated[
        list[str] | None,
        Query(description="Filter by severity level(s)"),
    ] = None,
    unacknowledged_only: Annotated[
        bool,
        Query(description="Only return unacknowledged anomalies"),
    ] = False,
    since: Annotated[
        datetime | None,
        Query(description="Filter anomalies from this time (ISO 8601)"),
    ] = None,
    until: Annotated[
        datetime | None,
        Query(description="Filter anomalies until this time (ISO 8601)"),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=500, description="Maximum number of results"),
    ] = 50,
    offset: Annotated[
        int,
        Query(ge=0, description="Number of results to skip"),
    ] = 0,
    db: AsyncSession = Depends(get_db),
) -> ZoneAnomalyListResponse:
    """List all zone anomalies across all zones.

    Returns a paginated list of anomalies with optional filtering by severity,
    acknowledgment status, and time range.

    Args:
        severity: Filter by one or more severity levels (info, warning, critical)
        unacknowledged_only: If True, only return unacknowledged anomalies
        since: Start time for the query (defaults to 24 hours ago)
        until: End time for the query (defaults to now)
        limit: Maximum number of results to return
        offset: Number of results to skip for pagination
        db: Database session

    Returns:
        ZoneAnomalyListResponse with list of anomalies and pagination info
    """
    # Default time range: last 24 hours
    if since is None:
        since = utc_now() - timedelta(hours=24)

    # Build query
    query = select(ZoneAnomaly).where(ZoneAnomaly.timestamp >= since)

    if until is not None:
        query = query.where(ZoneAnomaly.timestamp <= until)

    if severity:
        # Normalize severity values to lowercase
        normalized_severity = [s.lower() for s in severity]
        query = query.where(ZoneAnomaly.severity.in_(normalized_severity))

    if unacknowledged_only:
        query = query.where(ZoneAnomaly.acknowledged == False)  # noqa: E712

    # Get total count for pagination
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply ordering and pagination
    query = query.order_by(ZoneAnomaly.timestamp.desc())
    query = query.offset(offset).limit(limit)

    # Execute query
    result = await db.execute(query)
    anomalies = list(result.scalars().all())

    return ZoneAnomalyListResponse(
        items=anomalies,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + len(anomalies)) < total,
        ),
    )


@router.get("/{zone_id}/anomalies", response_model=ZoneAnomalyListResponse)
async def list_zone_anomalies(
    zone_id: str,
    severity: Annotated[
        list[str] | None,
        Query(description="Filter by severity level(s)"),
    ] = None,
    unacknowledged_only: Annotated[
        bool,
        Query(description="Only return unacknowledged anomalies"),
    ] = False,
    since: Annotated[
        datetime | None,
        Query(description="Filter anomalies from this time (ISO 8601)"),
    ] = None,
    until: Annotated[
        datetime | None,
        Query(description="Filter anomalies until this time (ISO 8601)"),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=500, description="Maximum number of results"),
    ] = 50,
    offset: Annotated[
        int,
        Query(ge=0, description="Number of results to skip"),
    ] = 0,
    db: AsyncSession = Depends(get_db),
) -> ZoneAnomalyListResponse:
    """List anomalies for a specific zone.

    Returns a paginated list of anomalies for the specified zone with optional
    filtering by severity, acknowledgment status, and time range.

    Args:
        zone_id: The zone ID to fetch anomalies for
        severity: Filter by one or more severity levels (info, warning, critical)
        unacknowledged_only: If True, only return unacknowledged anomalies
        since: Start time for the query (defaults to 24 hours ago)
        until: End time for the query (defaults to now)
        limit: Maximum number of results to return
        offset: Number of results to skip for pagination
        db: Database session

    Returns:
        ZoneAnomalyListResponse with list of anomalies and pagination info
    """
    # Default time range: last 24 hours
    if since is None:
        since = utc_now() - timedelta(hours=24)

    # Build query
    query = select(ZoneAnomaly).where(
        ZoneAnomaly.zone_id == zone_id,
        ZoneAnomaly.timestamp >= since,
    )

    if until is not None:
        query = query.where(ZoneAnomaly.timestamp <= until)

    if severity:
        # Normalize severity values to lowercase
        normalized_severity = [s.lower() for s in severity]
        query = query.where(ZoneAnomaly.severity.in_(normalized_severity))

    if unacknowledged_only:
        query = query.where(ZoneAnomaly.acknowledged == False)  # noqa: E712

    # Get total count for pagination
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply ordering and pagination
    query = query.order_by(ZoneAnomaly.timestamp.desc())
    query = query.offset(offset).limit(limit)

    # Execute query
    result = await db.execute(query)
    anomalies = list(result.scalars().all())

    return ZoneAnomalyListResponse(
        items=anomalies,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + len(anomalies)) < total,
        ),
    )


@router.post(
    "/anomalies/{anomaly_id}/acknowledge",
    response_model=ZoneAnomalyAcknowledgeResponse,
)
async def acknowledge_anomaly(
    anomaly_id: str,
    db: AsyncSession = Depends(get_db),
) -> ZoneAnomalyAcknowledgeResponse:
    """Acknowledge a zone anomaly.

    Marks the specified anomaly as acknowledged, indicating that a user
    has reviewed and acknowledged the alert.

    Args:
        anomaly_id: The anomaly ID to acknowledge
        db: Database session

    Returns:
        ZoneAnomalyAcknowledgeResponse with updated acknowledgment status

    Raises:
        HTTPException: 404 if anomaly not found
    """
    # Find the anomaly
    query = select(ZoneAnomaly).where(ZoneAnomaly.id == anomaly_id)
    result = await db.execute(query)
    anomaly = result.scalar_one_or_none()

    if anomaly is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Anomaly with ID '{anomaly_id}' not found",
        )

    # Acknowledge the anomaly
    anomaly.acknowledge()
    await db.commit()
    await db.refresh(anomaly)

    return ZoneAnomalyAcknowledgeResponse(
        id=anomaly.id,
        acknowledged=anomaly.acknowledged,
        acknowledged_at=anomaly.acknowledged_at,
        acknowledged_by=anomaly.acknowledged_by,
    )
