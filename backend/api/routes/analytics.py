"""API routes for analytics and reporting."""

from datetime import date as Date
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.analytics import (
    CameraUptimeDataPoint,
    CameraUptimeResponse,
    DetectionTrendDataPoint,
    DetectionTrendsResponse,
    ObjectDistributionDataPoint,
    ObjectDistributionResponse,
    RiskHistoryDataPoint,
    RiskHistoryResponse,
)
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event

logger = get_logger(__name__)
router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/detection-trends", response_model=DetectionTrendsResponse)
async def get_detection_trends(
    start_date: Date = Query(..., description="Start date for analytics (ISO format)"),
    end_date: Date = Query(..., description="End date for analytics (ISO format)"),
    db: AsyncSession = Depends(get_db),
) -> DetectionTrendsResponse:
    """Get detection counts aggregated by day.

    Returns daily detection counts for the specified date range.
    Creates one data point per day even if there are no detections.

    Args:
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
        db: Database session

    Returns:
        DetectionTrendsResponse with daily detection counts

    Raises:
        HTTPException: 400 if start_date is after end_date
    """
    # Validate date range
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before or equal to end_date",
        )

    # Query detection counts grouped by date
    # Cast detected_at (datetime with tz) to date for grouping
    query = (
        select(
            func.date(Detection.detected_at).label("detection_date"),
            func.count(Detection.id).label("detection_count"),
        )
        .where(
            func.date(Detection.detected_at) >= start_date,
            func.date(Detection.detected_at) <= end_date,
        )
        .group_by(func.date(Detection.detected_at))
        .order_by(func.date(Detection.detected_at))
    )

    result = await db.execute(query)
    rows = result.all()

    # Create a dictionary for fast lookup
    counts_by_date: dict[Date, int] = {row.detection_date: row.detection_count for row in rows}

    # Generate data points for every day in range (fill gaps with 0)
    data_points = []
    current_date = start_date
    total_detections = 0

    while current_date <= end_date:
        count = counts_by_date.get(current_date, 0)
        data_points.append(DetectionTrendDataPoint(date=current_date, count=count))
        total_detections += count
        current_date += timedelta(days=1)

    return DetectionTrendsResponse(
        data_points=data_points,
        total_detections=total_detections,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/risk-history", response_model=RiskHistoryResponse)
async def get_risk_history(
    start_date: Date = Query(..., description="Start date for analytics (ISO format)"),
    end_date: Date = Query(..., description="End date for analytics (ISO format)"),
    db: AsyncSession = Depends(get_db),
) -> RiskHistoryResponse:
    """Get risk score distribution over time.

    Returns daily counts of events grouped by risk level (low, medium, high, critical).
    Creates one data point per day even if there are no events.

    Args:
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
        db: Database session

    Returns:
        RiskHistoryResponse with daily risk level counts

    Raises:
        HTTPException: 400 if start_date is after end_date
    """
    # Validate date range
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before or equal to end_date",
        )

    # Query events grouped by date and risk_level
    # Cast started_at (datetime with tz) to date for grouping
    query = (
        select(
            func.date(Event.started_at).label("event_date"),
            Event.risk_level,
            func.count(Event.id).label("event_count"),
        )
        .where(
            func.date(Event.started_at) >= start_date,
            func.date(Event.started_at) <= end_date,
            Event.risk_level.isnot(None),  # Only include events with risk levels
        )
        .group_by(func.date(Event.started_at), Event.risk_level)
        .order_by(func.date(Event.started_at))
    )

    result = await db.execute(query)
    rows = result.all()

    # Create nested dictionary for fast lookup: {date: {risk_level: count}}
    counts_by_date: dict[Date, dict[str, int]] = {}
    for row in rows:
        if row.event_date not in counts_by_date:
            counts_by_date[row.event_date] = {}
        counts_by_date[row.event_date][row.risk_level] = row.event_count

    # Generate data points for every day in range (fill gaps with 0)
    data_points = []
    current_date = start_date

    while current_date <= end_date:
        risk_counts = counts_by_date.get(current_date, {})
        data_points.append(
            RiskHistoryDataPoint(
                date=current_date,
                low=risk_counts.get("low", 0),
                medium=risk_counts.get("medium", 0),
                high=risk_counts.get("high", 0),
                critical=risk_counts.get("critical", 0),
            )
        )
        current_date += timedelta(days=1)

    return RiskHistoryResponse(data_points=data_points, start_date=start_date, end_date=end_date)


@router.get("/camera-uptime", response_model=CameraUptimeResponse)
async def get_camera_uptime(
    start_date: Date = Query(..., description="Start date for analytics (ISO format)"),
    end_date: Date = Query(..., description="End date for analytics (ISO format)"),
    db: AsyncSession = Depends(get_db),
) -> CameraUptimeResponse:
    """Get uptime percentage per camera.

    Returns uptime percentage and detection count for each camera.
    Uptime is calculated based on the number of days with at least one detection
    divided by the total days in the date range.

    Args:
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
        db: Database session

    Returns:
        CameraUptimeResponse with per-camera uptime data

    Raises:
        HTTPException: 400 if start_date is after end_date
    """
    # Validate date range
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before or equal to end_date",
        )

    # Calculate total days in range
    total_days = (end_date - start_date).days + 1

    # Query cameras with their active days and detection counts
    # Active day = any day with at least one detection
    query = (
        select(
            Camera.id,
            Camera.name,
            func.count(func.distinct(func.date(Detection.detected_at))).label("active_days"),
            func.count(Detection.id).label("detection_count"),
        )
        .outerjoin(
            Detection,
            (Detection.camera_id == Camera.id)
            & (func.date(Detection.detected_at) >= start_date)
            & (func.date(Detection.detected_at) <= end_date),
        )
        .group_by(Camera.id, Camera.name)
        .order_by(Camera.name)
    )

    result = await db.execute(query)
    rows = result.all()

    # Build camera uptime data points
    cameras = []
    for row in rows:
        uptime_percentage = (row.active_days / total_days * 100.0) if total_days > 0 else 0.0
        cameras.append(
            CameraUptimeDataPoint(
                camera_id=row.id,
                camera_name=row.name,
                uptime_percentage=round(uptime_percentage, 2),
                detection_count=row.detection_count or 0,
            )
        )

    return CameraUptimeResponse(cameras=cameras, start_date=start_date, end_date=end_date)


@router.get("/object-distribution", response_model=ObjectDistributionResponse)
async def get_object_distribution(
    start_date: Date = Query(..., description="Start date for analytics (ISO format)"),
    end_date: Date = Query(..., description="End date for analytics (ISO format)"),
    db: AsyncSession = Depends(get_db),
) -> ObjectDistributionResponse:
    """Get detection counts by object type.

    Returns detection counts grouped by object type with percentages.
    Only includes detections with non-null object_type.

    Args:
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
        db: Database session

    Returns:
        ObjectDistributionResponse with object type counts and percentages

    Raises:
        HTTPException: 400 if start_date is after end_date
    """
    # Validate date range
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before or equal to end_date",
        )

    # Query detection counts grouped by object_type
    query = (
        select(Detection.object_type, func.count(Detection.id).label("object_count"))
        .where(
            func.date(Detection.detected_at) >= start_date,
            func.date(Detection.detected_at) <= end_date,
            Detection.object_type.isnot(None),  # Only include detections with object types
        )
        .group_by(Detection.object_type)
        .order_by(func.count(Detection.id).desc())
    )

    result = await db.execute(query)
    rows = result.all()

    # Calculate total detections
    total_detections: int = sum(row.object_count for row in rows)

    # Build object distribution data points with percentages
    object_types = []
    for row in rows:
        obj_count: int = row.object_count
        percentage = (obj_count / total_detections * 100.0) if total_detections > 0 else 0.0
        object_types.append(
            ObjectDistributionDataPoint(
                object_type=row.object_type,
                count=obj_count,
                percentage=round(percentage, 2),
            )
        )

    return ObjectDistributionResponse(
        object_types=object_types,
        total_detections=total_detections,
        start_date=start_date,
        end_date=end_date,
    )
