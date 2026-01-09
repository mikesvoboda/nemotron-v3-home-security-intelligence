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


@router.get(
    "/detection-trends",
    response_model=DetectionTrendsResponse,
    summary="Get detection trends over time",
    description="""
Retrieve detection counts aggregated by day for a specified date range.

This endpoint is useful for:
- Monitoring detection activity over time
- Identifying patterns in security events
- Dashboard trend visualizations

The response includes one data point per day, with zero-fill for days without detections.
Date parameters should be in ISO 8601 format (YYYY-MM-DD).
""",
    operation_id="getDetectionTrends",
    responses={
        200: {
            "description": "Successfully retrieved detection trends",
            "content": {
                "application/json": {
                    "example": {
                        "data_points": [
                            {"date": "2025-01-01", "count": 20},
                            {"date": "2025-01-02", "count": 25},
                            {"date": "2025-01-03", "count": 18},
                        ],
                        "total_detections": 63,
                        "start_date": "2025-01-01",
                        "end_date": "2025-01-03",
                    }
                }
            },
        },
        400: {
            "description": "Bad request - start_date is after end_date",
            "content": {
                "application/json": {
                    "example": {"detail": "start_date must be before or equal to end_date"}
                }
            },
        },
        422: {
            "description": "Validation error - invalid date format or missing required parameters"
        },
        500: {"description": "Internal server error"},
    },
)
async def get_detection_trends(
    start_date: Date = Query(
        ...,
        description="Start date for analytics (inclusive, ISO 8601 format: YYYY-MM-DD)",
        examples=["2025-01-01"],
    ),
    end_date: Date = Query(
        ...,
        description="End date for analytics (inclusive, ISO 8601 format: YYYY-MM-DD)",
        examples=["2025-01-07"],
    ),
    db: AsyncSession = Depends(get_db),
) -> DetectionTrendsResponse:
    """Get detection counts aggregated by day.

    Returns daily detection counts for the specified date range.
    Creates one data point per day even if there are no detections,
    ensuring consistent time series data for charting.

    Use cases:
    - Dashboard trend charts showing detection volume over time
    - Security analysis to identify unusual activity patterns
    - Historical reporting and auditing

    Args:
        start_date: Start date (inclusive), ISO 8601 format
        end_date: End date (inclusive), ISO 8601 format
        db: Database session (injected)

    Returns:
        DetectionTrendsResponse with:
        - data_points: List of daily detection counts
        - total_detections: Sum of all detections in range
        - start_date: Requested start date
        - end_date: Requested end date

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
    summary="Get risk score distribution over time",
    description="""
Retrieve daily counts of events grouped by risk level for a specified date range.

Risk levels:
- **low**: Risk score 0-25 (routine activity)
- **medium**: Risk score 26-50 (noteworthy events)
- **high**: Risk score 51-75 (concerning activity)
- **critical**: Risk score 76-100 (immediate attention required)

This endpoint is useful for:
- Security posture assessment over time
- Risk trend analysis and reporting
- Identifying periods of elevated security concern

The response includes one data point per day, with zero counts for levels with no events.
""",
    operation_id="getRiskHistory",
    responses={
        200: {
            "description": "Successfully retrieved risk history",
            "content": {
                "application/json": {
                    "example": {
                        "data_points": [
                            {
                                "date": "2025-01-01",
                                "low": 10,
                                "medium": 5,
                                "high": 2,
                                "critical": 1,
                            },
                            {
                                "date": "2025-01-02",
                                "low": 12,
                                "medium": 4,
                                "high": 3,
                                "critical": 0,
                            },
                        ],
                        "start_date": "2025-01-01",
                        "end_date": "2025-01-02",
                    }
                }
            },
        },
        400: {
            "description": "Bad request - start_date is after end_date",
            "content": {
                "application/json": {
                    "example": {"detail": "start_date must be before or equal to end_date"}
                }
            },
        },
        422: {
            "description": "Validation error - invalid date format or missing required parameters"
        },
        500: {"description": "Internal server error"},
    },
)
async def get_risk_history(
    start_date: Date = Query(
        ...,
        description="Start date for analytics (inclusive, ISO 8601 format: YYYY-MM-DD)",
        examples=["2025-01-01"],
    ),
    end_date: Date = Query(
        ...,
        description="End date for analytics (inclusive, ISO 8601 format: YYYY-MM-DD)",
        examples=["2025-01-07"],
    ),
    db: AsyncSession = Depends(get_db),
) -> RiskHistoryResponse:
    """Get risk score distribution over time.

    Returns daily counts of events grouped by risk level (low, medium, high, critical).
    Creates one data point per day even if there are no events, ensuring consistent
    time series data for stacked bar charts and area graphs.

    Risk level thresholds:
    - low: 0-25 (routine, expected activity)
    - medium: 26-50 (noteworthy but not urgent)
    - high: 51-75 (concerning, requires attention)
    - critical: 76-100 (immediate response required)

    Use cases:
    - Security dashboard risk trend visualization
    - Compliance reporting on security posture
    - Identifying periods requiring investigation

    Args:
        start_date: Start date (inclusive), ISO 8601 format
        end_date: End date (inclusive), ISO 8601 format
        db: Database session (injected)

    Returns:
        RiskHistoryResponse with:
        - data_points: List of daily risk level counts
        - start_date: Requested start date
        - end_date: Requested end date

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
    summary="Get camera uptime statistics",
    description="""
Retrieve uptime percentage and detection counts for each camera over a specified date range.

Uptime calculation:
- A camera is considered "active" on a day if it recorded at least one detection
- Uptime percentage = (active days / total days in range) * 100
- Cameras with no detections in the range will show 0% uptime

This endpoint is useful for:
- Monitoring camera health and reliability
- Identifying offline or malfunctioning cameras
- Infrastructure maintenance planning

All registered cameras are included in the response, even those with 0% uptime.
""",
    operation_id="getCameraUptime",
    responses={
        200: {
            "description": "Successfully retrieved camera uptime statistics",
            "content": {
                "application/json": {
                    "example": {
                        "cameras": [
                            {
                                "camera_id": "front_door",
                                "camera_name": "Front Door",
                                "uptime_percentage": 98.5,
                                "detection_count": 150,
                            },
                            {
                                "camera_id": "back_door",
                                "camera_name": "Back Door",
                                "uptime_percentage": 95.2,
                                "detection_count": 120,
                            },
                        ],
                        "start_date": "2025-01-01",
                        "end_date": "2025-01-07",
                    }
                }
            },
        },
        400: {
            "description": "Bad request - start_date is after end_date",
            "content": {
                "application/json": {
                    "example": {"detail": "start_date must be before or equal to end_date"}
                }
            },
        },
        422: {
            "description": "Validation error - invalid date format or missing required parameters"
        },
        500: {"description": "Internal server error"},
    },
)
async def get_camera_uptime(
    start_date: Date = Query(
        ...,
        description="Start date for analytics (inclusive, ISO 8601 format: YYYY-MM-DD)",
        examples=["2025-01-01"],
    ),
    end_date: Date = Query(
        ...,
        description="End date for analytics (inclusive, ISO 8601 format: YYYY-MM-DD)",
        examples=["2025-01-07"],
    ),
    db: AsyncSession = Depends(get_db),
) -> CameraUptimeResponse:
    """Get uptime percentage per camera.

    Returns uptime percentage and detection count for each camera.
    Uptime is calculated based on the number of days with at least one detection
    divided by the total days in the date range.

    A camera with 100% uptime recorded at least one detection every day.
    A camera with 0% uptime had no detections in the entire date range.

    Use cases:
    - Camera health monitoring dashboard
    - Maintenance scheduling and alerts
    - SLA compliance reporting

    Args:
        start_date: Start date (inclusive), ISO 8601 format
        end_date: End date (inclusive), ISO 8601 format
        db: Database session (injected)

    Returns:
        CameraUptimeResponse with:
        - cameras: List of camera uptime data points
        - start_date: Requested start date
        - end_date: Requested end date

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
    summary="Get detection counts by object type",
    description="""
Retrieve detection counts grouped by object type for a specified date range.

Common object types detected by RT-DETRv2:
- **person**: Human beings
- **car**, **truck**, **motorcycle**: Vehicles
- **dog**, **cat**: Pets and animals
- **bicycle**: Non-motorized vehicles

This endpoint is useful for:
- Understanding what types of objects trigger detections
- Tuning detection sensitivity by object type
- Security pattern analysis (e.g., vehicle vs pedestrian traffic)

Results are sorted by count (highest first) and include percentage of total.
Detections without an object_type are excluded from results.
""",
    operation_id="getObjectDistribution",
    responses={
        200: {
            "description": "Successfully retrieved object distribution",
            "content": {
                "application/json": {
                    "example": {
                        "object_types": [
                            {"object_type": "person", "count": 120, "percentage": 45.5},
                            {"object_type": "car", "count": 80, "percentage": 30.3},
                            {"object_type": "dog", "count": 64, "percentage": 24.2},
                        ],
                        "total_detections": 264,
                        "start_date": "2025-01-01",
                        "end_date": "2025-01-07",
                    }
                }
            },
        },
        400: {
            "description": "Bad request - start_date is after end_date",
            "content": {
                "application/json": {
                    "example": {"detail": "start_date must be before or equal to end_date"}
                }
            },
        },
        422: {
            "description": "Validation error - invalid date format or missing required parameters"
        },
        500: {"description": "Internal server error"},
    },
)
async def get_object_distribution(
    start_date: Date = Query(
        ...,
        description="Start date for analytics (inclusive, ISO 8601 format: YYYY-MM-DD)",
        examples=["2025-01-01"],
    ),
    end_date: Date = Query(
        ...,
        description="End date for analytics (inclusive, ISO 8601 format: YYYY-MM-DD)",
        examples=["2025-01-07"],
    ),
    db: AsyncSession = Depends(get_db),
) -> ObjectDistributionResponse:
    """Get detection counts by object type.

    Returns detection counts grouped by object type with percentages,
    sorted by count in descending order. Object types are determined
    by the RT-DETRv2 detection model (COCO-based labels).

    Common object types include: person, car, truck, motorcycle,
    bicycle, dog, cat, bird, and other COCO dataset categories.

    Use cases:
    - Pie charts or bar graphs showing object type breakdown
    - Detection filter tuning (e.g., ignore certain object types)
    - Traffic pattern analysis

    Args:
        start_date: Start date (inclusive), ISO 8601 format
        end_date: End date (inclusive), ISO 8601 format
        db: Database session (injected)

    Returns:
        ObjectDistributionResponse with:
        - object_types: List of object type counts with percentages
        - total_detections: Sum of all detections with object types
        - start_date: Requested start date
        - end_date: Requested end date

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
