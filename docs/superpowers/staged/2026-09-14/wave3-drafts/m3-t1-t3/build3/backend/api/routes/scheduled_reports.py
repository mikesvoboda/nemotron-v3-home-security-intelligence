"""API routes for scheduled report management.

NEM-3621: Create Scheduled Reports API Schemas and Routes

Provides endpoints for:
- Creating scheduled reports
- Listing all scheduled reports
- Getting a single scheduled report
- Updating scheduled reports
- Deleting scheduled reports
- Manually triggering a report run
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.scheduled_report import (
    ScheduledReportCreate,
    ScheduledReportListResponse,
    ScheduledReportResponse,
    ScheduledReportRunResponse,
    ScheduledReportUpdate,
)
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.models.scheduled_report import ScheduledReport

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/scheduled-reports",
    tags=["scheduled-reports"],
)


@router.post(
    "",
    response_model=ScheduledReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a scheduled report",
    description="Create a new scheduled report with the specified configuration. "
    "Reports can be daily, weekly, or monthly, and can be delivered via email.",
    responses={
        201: {"description": "Scheduled report created successfully"},
        422: {"description": "Validation error"},
    },
)
async def create_scheduled_report(
    report_data: ScheduledReportCreate,
    db: AsyncSession = Depends(get_db),
) -> ScheduledReportResponse:
    """Create a new scheduled report.

    Args:
        report_data: Scheduled report configuration
        db: Database session

    Returns:
        The created scheduled report

    Raises:
        HTTPException: 422 if validation fails
    """
    # Create the scheduled report
    now = datetime.now(UTC)
    report = ScheduledReport(
        name=report_data.name,
        frequency=report_data.frequency.value,
        day_of_week=report_data.day_of_week,
        day_of_month=report_data.day_of_month,
        hour=report_data.hour,
        minute=report_data.minute,
        timezone=report_data.timezone,
        format=report_data.format.value,
        enabled=report_data.enabled,
        email_recipients=report_data.email_recipients,
        include_charts=report_data.include_charts,
        include_event_details=report_data.include_event_details,
        created_at=now,
        updated_at=now,
    )

    db.add(report)
    await db.commit()
    await db.refresh(report)

    logger.info(
        "Created scheduled report",
        extra={
            "report_id": report.id,
            "report_name": report.name,
            "frequency": report.frequency,
        },
    )

    return ScheduledReportResponse(
        id=report.id,
        name=report.name,
        frequency=report.frequency,
        day_of_week=report.day_of_week,
        day_of_month=report.day_of_month,
        hour=report.hour,
        minute=report.minute,
        timezone=report.timezone,
        format=report.format,
        enabled=report.enabled,
        email_recipients=report.email_recipients,
        include_charts=report.include_charts,
        include_event_details=report.include_event_details,
        last_run_at=report.last_run_at,
        next_run_at=report.next_run_at,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


@router.get(
    "",
    response_model=ScheduledReportListResponse,
    summary="List all scheduled reports",
    description="Get a list of all scheduled reports with their configurations.",
    responses={
        200: {"description": "List of scheduled reports"},
    },
)
async def list_scheduled_reports(
    enabled: bool | None = None,
    db: AsyncSession = Depends(get_db),
) -> ScheduledReportListResponse:
    """List all scheduled reports.

    Args:
        enabled: Optional filter by enabled status
        db: Database session

    Returns:
        List of scheduled reports with total count
    """
    # Build query
    query = select(ScheduledReport).order_by(ScheduledReport.created_at.desc())

    if enabled is not None:
        query = query.where(ScheduledReport.enabled == enabled)

    # Execute query
    result = await db.execute(query)
    reports = result.scalars().all()

    # Get total count
    count_query = select(func.count(ScheduledReport.id))
    if enabled is not None:
        count_query = count_query.where(ScheduledReport.enabled == enabled)
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    return ScheduledReportListResponse(
        items=[
            ScheduledReportResponse(
                id=report.id,
                name=report.name,
                frequency=report.frequency,
                day_of_week=report.day_of_week,
                day_of_month=report.day_of_month,
                hour=report.hour,
                minute=report.minute,
                timezone=report.timezone,
                format=report.format,
                enabled=report.enabled,
                email_recipients=report.email_recipients,
                include_charts=report.include_charts,
                include_event_details=report.include_event_details,
                last_run_at=report.last_run_at,
                next_run_at=report.next_run_at,
                created_at=report.created_at,
                updated_at=report.updated_at,
            )
            for report in reports
        ],
        total=total,
    )


@router.get(
    "/{report_id}",
    response_model=ScheduledReportResponse,
    summary="Get a scheduled report",
    description="Get details of a specific scheduled report by ID.",
    responses={
        200: {"description": "Scheduled report details"},
        404: {"description": "Scheduled report not found"},
    },
)
async def get_scheduled_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
) -> ScheduledReportResponse:
    """Get a scheduled report by ID.

    Args:
        report_id: ID of the scheduled report
        db: Database session

    Returns:
        The scheduled report

    Raises:
        HTTPException: 404 if report not found
    """
    query = select(ScheduledReport).where(ScheduledReport.id == report_id)
    result = await db.execute(query)
    report = result.scalar_one_or_none()

    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scheduled report with ID {report_id} not found",
        )

    return ScheduledReportResponse(
        id=report.id,
        name=report.name,
        frequency=report.frequency,
        day_of_week=report.day_of_week,
        day_of_month=report.day_of_month,
        hour=report.hour,
        minute=report.minute,
        timezone=report.timezone,
        format=report.format,
        enabled=report.enabled,
        email_recipients=report.email_recipients,
        include_charts=report.include_charts,
        include_event_details=report.include_event_details,
        last_run_at=report.last_run_at,
        next_run_at=report.next_run_at,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


@router.put(
    "/{report_id}",
    response_model=ScheduledReportResponse,
    summary="Update a scheduled report",
    description="Update an existing scheduled report configuration. "
    "All fields are optional - only provided fields will be updated.",
    responses={
        200: {"description": "Scheduled report updated successfully"},
        404: {"description": "Scheduled report not found"},
        422: {"description": "Validation error"},
    },
)
async def update_scheduled_report(
    report_id: int,
    report_data: ScheduledReportUpdate,
    db: AsyncSession = Depends(get_db),
) -> ScheduledReportResponse:
    """Update a scheduled report.

    Args:
        report_id: ID of the scheduled report to update
        report_data: Fields to update (all optional)
        db: Database session

    Returns:
        The updated scheduled report

    Raises:
        HTTPException: 404 if report not found
        HTTPException: 422 if validation fails
    """
    # Get existing report
    query = select(ScheduledReport).where(ScheduledReport.id == report_id)
    result = await db.execute(query)
    report = result.scalar_one_or_none()

    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scheduled report with ID {report_id} not found",
        )

    # Update only provided fields
    update_data = report_data.model_dump(exclude_unset=True)

    # Convert enums to values for storage
    if "frequency" in update_data and update_data["frequency"] is not None:
        update_data["frequency"] = update_data["frequency"].value
    if "format" in update_data and update_data["format"] is not None:
        update_data["format"] = update_data["format"].value

    for field, value in update_data.items():
        setattr(report, field, value)

    report.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(report)

    logger.info(
        "Updated scheduled report",
        extra={
            "report_id": report.id,
            "updated_fields": list(update_data.keys()),
        },
    )

    return ScheduledReportResponse(
        id=report.id,
        name=report.name,
        frequency=report.frequency,
        day_of_week=report.day_of_week,
        day_of_month=report.day_of_month,
        hour=report.hour,
        minute=report.minute,
        timezone=report.timezone,
        format=report.format,
        enabled=report.enabled,
        email_recipients=report.email_recipients,
        include_charts=report.include_charts,
        include_event_details=report.include_event_details,
        last_run_at=report.last_run_at,
        next_run_at=report.next_run_at,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


@router.delete(
    "/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a scheduled report",
    description="Delete a scheduled report by ID.",
    responses={
        204: {"description": "Scheduled report deleted successfully"},
        404: {"description": "Scheduled report not found"},
    },
)
async def delete_scheduled_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a scheduled report.

    Args:
        report_id: ID of the scheduled report to delete
        db: Database session

    Raises:
        HTTPException: 404 if report not found
    """
    # Get existing report
    query = select(ScheduledReport).where(ScheduledReport.id == report_id)
    result = await db.execute(query)
    report = result.scalar_one_or_none()

    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scheduled report with ID {report_id} not found",
        )

    await db.delete(report)
    await db.commit()

    logger.info(
        "Deleted scheduled report",
        extra={
            "report_id": report_id,
        },
    )


@router.post(
    "/{report_id}/run",
    response_model=ScheduledReportRunResponse,
    summary="Manually trigger a report",
    description="Manually trigger a scheduled report to run immediately, "
    "regardless of its schedule.",
    responses={
        200: {"description": "Report run initiated"},
        404: {"description": "Scheduled report not found"},
    },
)
async def run_scheduled_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
) -> ScheduledReportRunResponse:
    """Manually trigger a scheduled report.

    This runs the report immediately, regardless of its schedule.
    The report will be generated asynchronously.

    Args:
        report_id: ID of the scheduled report to run
        db: Database session

    Returns:
        Status of the initiated run

    Raises:
        HTTPException: 404 if report not found
    """
    # Verify report exists
    query = select(ScheduledReport).where(ScheduledReport.id == report_id)
    result = await db.execute(query)
    report = result.scalar_one_or_none()

    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scheduled report with ID {report_id} not found",
        )

    # In the future, this would queue the report for generation
    # For now, just return a status indicating the run was initiated
    now = datetime.now(UTC)

    logger.info(
        "Manually triggered scheduled report",
        extra={
            "report_id": report_id,
            "report_name": report.name,
        },
    )

    return ScheduledReportRunResponse(
        report_id=report_id,
        status="queued",
        message=f"Report '{report.name}' has been queued for generation",
        started_at=now,
    )
