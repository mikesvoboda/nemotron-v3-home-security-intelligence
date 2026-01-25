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
    RiskScoreDistributionBucket,
    RiskScoreDistributionResponse,
    RiskScoreTrendDataPoint,
    RiskScoreTrendsResponse,
)
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event

logger = get_logger(__name__)
router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get(
    "/detection-trends",
    response_model=DetectionTrendsResponse,
    responses={
        400: {"description": "Bad request - Invalid date range"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
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


@router.get(
    "/risk-history",
    response_model=RiskHistoryResponse,
    responses={
        400: {"description": "Bad request - Invalid date range"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
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


@router.get(
    "/camera-uptime",
    response_model=CameraUptimeResponse,
    responses={
        400: {"description": "Bad request - Invalid date range"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
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


@router.get(
    "/object-distribution",
    response_model=ObjectDistributionResponse,
    responses={
        400: {"description": "Bad request - Invalid date range"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
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


@router.get(
    "/risk-score-distribution",
    response_model=RiskScoreDistributionResponse,
    responses={
        400: {"description": "Bad request - Invalid date range or bucket size"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def get_risk_score_distribution(
    start_date: Date = Query(..., description="Start date for analytics (ISO format)"),
    end_date: Date = Query(..., description="End date for analytics (ISO format)"),
    bucket_size: int = Query(
        10, description="Size of each score bucket (default: 10)", ge=1, le=50
    ),
    db: AsyncSession = Depends(get_db),
) -> RiskScoreDistributionResponse:
    """Get risk score distribution as a histogram.

    Returns counts of events grouped into score buckets (e.g., 0-10, 10-20, ..., 90-100).
    Only includes events with non-null risk_score.

    Args:
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
        bucket_size: Size of each bucket (default 10 for buckets 0-10, 10-20, etc.)
        db: Database session

    Returns:
        RiskScoreDistributionResponse with histogram buckets

    Raises:
        HTTPException: 400 if start_date is after end_date
    """
    # Validate date range
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before or equal to end_date",
        )

    # Calculate number of buckets (100 / bucket_size, ensuring last bucket includes 100)
    num_buckets = 100 // bucket_size

    # Query events grouped by score bucket
    # Use floor division to assign scores to buckets
    # Score 100 goes to the last bucket (handled by LEAST to cap at num_buckets-1)
    bucket_expr = func.least(Event.risk_score / bucket_size, num_buckets - 1)
    query = (
        select(
            bucket_expr.label("bucket"),
            func.count(Event.id).label("count"),
        )
        .where(
            func.date(Event.started_at) >= start_date,
            func.date(Event.started_at) <= end_date,
            Event.risk_score.isnot(None),  # Only include events with risk scores
            Event.deleted_at.is_(None),  # Exclude soft-deleted events
        )
        .group_by(bucket_expr)
        .order_by(bucket_expr)
    )

    result = await db.execute(query)
    rows = result.all()

    # Create dictionary for fast lookup
    # mypy incorrectly infers row.count as Callable due to SQLAlchemy Row type
    counts_by_bucket: dict[int, int] = {
        int(row.bucket): int(row.count)  # type: ignore[call-overload]
        for row in rows
    }

    # Generate all buckets (fill gaps with 0)
    buckets = []
    total_events = 0

    for i in range(num_buckets):
        min_score = i * bucket_size
        # Last bucket includes 100
        max_score = min_score + bucket_size if i < num_buckets - 1 else 100
        count = counts_by_bucket.get(i, 0)
        buckets.append(
            RiskScoreDistributionBucket(
                min_score=min_score,
                max_score=max_score,
                count=count,
            )
        )
        total_events += count

    return RiskScoreDistributionResponse(
        buckets=buckets,
        total_events=total_events,
        start_date=start_date,
        end_date=end_date,
        bucket_size=bucket_size,
    )


@router.get(
    "/risk-score-trends",
    response_model=RiskScoreTrendsResponse,
    responses={
        400: {"description": "Bad request - Invalid date range"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def get_risk_score_trends(
    start_date: Date = Query(..., description="Start date for analytics (ISO format)"),
    end_date: Date = Query(..., description="End date for analytics (ISO format)"),
    db: AsyncSession = Depends(get_db),
) -> RiskScoreTrendsResponse:
    """Get average risk score trends over time.

    Returns daily average risk scores for the specified date range.
    Creates one data point per day even if there are no events.

    Args:
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
        db: Database session

    Returns:
        RiskScoreTrendsResponse with daily average scores and event counts

    Raises:
        HTTPException: 400 if start_date is after end_date
    """
    # Validate date range
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before or equal to end_date",
        )

    # Query events grouped by date with average risk score
    query = (
        select(
            func.date(Event.started_at).label("event_date"),
            func.avg(Event.risk_score).label("avg_score"),
            func.count(Event.id).label("count"),
        )
        .where(
            func.date(Event.started_at) >= start_date,
            func.date(Event.started_at) <= end_date,
            Event.risk_score.isnot(None),  # Only include events with risk scores
            Event.deleted_at.is_(None),  # Exclude soft-deleted events
        )
        .group_by(func.date(Event.started_at))
        .order_by(func.date(Event.started_at))
    )

    result = await db.execute(query)
    rows = result.all()

    # Create dictionary for fast lookup
    # mypy incorrectly infers row.count as Callable due to SQLAlchemy Row type
    data_by_date: dict[Date, tuple[float, int]] = {
        row.event_date: (float(row.avg_score), int(row.count))  # type: ignore[call-overload]
        for row in rows
    }

    # Generate data points for every day in range (fill gaps with 0)
    data_points = []
    current_date = start_date

    while current_date <= end_date:
        if current_date in data_by_date:
            avg_score, count = data_by_date[current_date]
            data_points.append(
                RiskScoreTrendDataPoint(
                    date=current_date,
                    avg_score=round(avg_score, 1),
                    count=count,
                )
            )
        else:
            data_points.append(
                RiskScoreTrendDataPoint(
                    date=current_date,
                    avg_score=0.0,
                    count=0,
                )
            )
        current_date += timedelta(days=1)

    return RiskScoreTrendsResponse(
        data_points=data_points,
        start_date=start_date,
        end_date=end_date,
    )
