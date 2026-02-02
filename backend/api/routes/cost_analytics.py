"""API routes for cost analytics.

This module provides endpoints for the Cost Analytics Dashboard,
exposing token costs, GPU costs, budget utilization, and cost trends.

Part of NEM-5024 Phase 2: Cost Analytics Dashboard.
"""

from datetime import UTC, datetime, timedelta
from datetime import date as Date

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import ORJSONResponse

from backend.api.schemas.cost_analytics import (
    BudgetUtilization,
    CostAnalyticsResponse,
    CostEfficiencyMetrics,
    CostTrendDataPoint,
    CostTrendResponse,
    DailyCostEntry,
    ModelCostBreakdown,
    PricingConfig,
    TokenUsageMetrics,
)
from backend.core.logging import get_logger
from backend.services.cost_tracker import CostTracker, DailyUsage, get_cost_tracker

logger = get_logger(__name__)
router = APIRouter(
    prefix="/api/analytics/costs",
    tags=["cost-analytics"],
    default_response_class=ORJSONResponse,
)

# Maximum allowed date range for cost trend queries
MAX_DATE_RANGE_DAYS = 90


def _validate_date_range(start_date: Date, end_date: Date) -> None:
    """Validate cost analytics date range.

    Args:
        start_date: Start date (inclusive)
        end_date: End date (inclusive)

    Raises:
        HTTPException: 400 if validation fails
    """
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before or equal to end_date",
        )

    date_range_days = (end_date - start_date).days + 1
    if date_range_days > MAX_DATE_RANGE_DAYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Date range exceeds maximum allowed ({MAX_DATE_RANGE_DAYS} days). "
            f"Requested range: {date_range_days} days.",
        )


@router.get(
    "",
    response_model=CostAnalyticsResponse,
    responses={
        200: {"description": "Cost analytics data"},
        500: {"description": "Internal server error"},
    },
)
async def get_cost_analytics() -> CostAnalyticsResponse:
    """Get comprehensive cost analytics data.

    Returns cost metrics including:
    - Today's cost summary
    - Daily and monthly budget utilization
    - Token usage metrics
    - Cost breakdown by model
    - Cost efficiency metrics
    - Historical cost data (last 30 days)
    - Pricing configuration

    Returns:
        CostAnalyticsResponse with all cost metrics
    """
    tracker = get_cost_tracker()
    now = datetime.now(UTC)
    today = now.date()

    # Get today's usage
    today_usage = tracker.get_daily_usage(today)

    # Build today's cost entry
    today_entry = DailyCostEntry(
        date=today.isoformat(),
        total_cost_usd=today_usage.total_estimated_cost_usd if today_usage else 0.0,
        token_cost_usd=_calculate_token_cost(today_usage) if today_usage else 0.0,
        gpu_cost_usd=_calculate_gpu_cost(today_usage) if today_usage else 0.0,
        event_count=today_usage.event_count if today_usage else 0,
        detection_count=today_usage.total_images_processed if today_usage else 0,
    )

    # Get budget status
    budget_status = await tracker.get_budget_status()

    # Build budget utilization responses
    daily_budget = BudgetUtilization(
        period="daily",
        limit_usd=budget_status.daily_limit_usd,
        used_usd=budget_status.daily_used_usd,
        remaining_usd=budget_status.daily_remaining_usd,
        utilization_ratio=budget_status.daily_utilization_ratio,
        exceeded=budget_status.daily_exceeded,
        warning_reached=budget_status.warning_threshold_reached,
    )

    monthly_budget = BudgetUtilization(
        period="monthly",
        limit_usd=budget_status.monthly_limit_usd,
        used_usd=budget_status.monthly_used_usd,
        remaining_usd=budget_status.monthly_remaining_usd,
        utilization_ratio=budget_status.monthly_utilization_ratio,
        exceeded=budget_status.monthly_exceeded,
        warning_reached=budget_status.warning_threshold_reached,
    )

    # Get token usage metrics
    summary = tracker.get_usage_summary()
    token_usage = TokenUsageMetrics(
        input_tokens=summary["today"]["input_tokens"],
        output_tokens=summary["today"]["output_tokens"],
        total_tokens=summary["today"]["input_tokens"] + summary["today"]["output_tokens"],
        token_cost_usd=_calculate_token_cost(today_usage) if today_usage else 0.0,
    )

    # Get cost breakdown by model
    cost_by_model = _build_model_cost_breakdown(today_usage)

    # Get efficiency metrics
    efficiency = CostEfficiencyMetrics(
        cost_per_detection_usd=summary["all_time"]["avg_cost_per_event_usd"] * 0.1,  # Approximation
        cost_per_event_usd=summary["all_time"]["avg_cost_per_event_usd"],
        total_detections=sum(
            u.total_images_processed
            for u in [tracker.get_daily_usage(today - timedelta(days=i)) for i in range(30)]
            if u
        ),
        total_events=summary["all_time"]["total_events"],
    )

    # Get historical cost data (last 30 days)
    cost_history = _build_cost_history(tracker, today, 30)

    # Get pricing configuration
    pricing = PricingConfig(
        input_cost_per_1k_tokens=summary["pricing"]["input_cost_per_1k_tokens"],
        output_cost_per_1k_tokens=summary["pricing"]["output_cost_per_1k_tokens"],
        gpu_cost_per_second=summary["pricing"]["gpu_cost_per_second"],
        detection_cost_per_image=0.00002,  # From CloudPricing default
        enrichment_cost_per_operation=0.00001,  # From CloudPricing default
    )

    return CostAnalyticsResponse(
        today=today_entry,
        daily_budget=daily_budget,
        monthly_budget=monthly_budget,
        token_usage=token_usage,
        cost_by_model=cost_by_model,
        efficiency=efficiency,
        cost_history=cost_history,
        pricing=pricing,
        last_updated=now.isoformat(),
    )


@router.get(
    "/trends",
    response_model=CostTrendResponse,
    responses={
        200: {"description": "Cost trend data"},
        400: {"description": "Bad request - Invalid date range"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def get_cost_trends(
    start_date: Date = Query(..., description="Start date for trends (ISO format)"),
    end_date: Date = Query(..., description="End date for trends (ISO format)"),
) -> CostTrendResponse:
    """Get cost trends over a date range.

    Returns daily cost totals for the specified date range,
    suitable for trend visualization.

    Args:
        start_date: Start date (inclusive)
        end_date: End date (inclusive)

    Returns:
        CostTrendResponse with daily cost data points
    """
    _validate_date_range(start_date, end_date)

    tracker = get_cost_tracker()
    data_points: list[CostTrendDataPoint] = []
    total_cost = 0.0

    current_date = start_date
    while current_date <= end_date:
        usage = tracker.get_daily_usage(current_date)
        cost = usage.total_estimated_cost_usd if usage else 0.0
        data_points.append(
            CostTrendDataPoint(
                date=current_date.isoformat(),
                cost_usd=cost,
            )
        )
        total_cost += cost
        current_date += timedelta(days=1)

    return CostTrendResponse(
        data_points=data_points,
        total_cost_usd=total_cost,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
    )


def _calculate_token_cost(usage: DailyUsage | None) -> float:
    """Calculate token-related cost from usage data."""
    if not usage:
        return 0.0
    tracker = get_cost_tracker()
    pricing = tracker._pricing
    input_cost = (usage.total_input_tokens / 1000.0) * pricing.input_cost_per_1k_tokens
    output_cost = (usage.total_output_tokens / 1000.0) * pricing.output_cost_per_1k_tokens
    return float(input_cost + output_cost)


def _calculate_gpu_cost(usage: DailyUsage | None) -> float:
    """Calculate GPU-related cost from usage data."""
    if not usage:
        return 0.0
    tracker = get_cost_tracker()
    return float(usage.total_gpu_seconds * tracker._pricing.gpu_cost_per_second)


def _build_model_cost_breakdown(usage: DailyUsage | None) -> list[ModelCostBreakdown]:
    """Build cost breakdown by model from usage data."""
    if not usage or not usage.usage_by_model:
        return []

    return [
        ModelCostBreakdown(
            model=model,
            cost_usd=cost,
            gpu_seconds=0.0,  # Not tracked per-model currently
            request_count=0,  # Not tracked per-model currently
        )
        for model, cost in usage.usage_by_model.items()
    ]


def _build_cost_history(tracker: CostTracker, end_date: Date, days: int) -> list[DailyCostEntry]:
    """Build historical cost data for the last N days."""
    history = []
    for i in range(days - 1, -1, -1):  # Start from oldest
        target_date = end_date - timedelta(days=i)
        usage = tracker.get_daily_usage(target_date)
        history.append(
            DailyCostEntry(
                date=target_date.isoformat(),
                total_cost_usd=usage.total_estimated_cost_usd if usage else 0.0,
                token_cost_usd=_calculate_token_cost(usage),
                gpu_cost_usd=_calculate_gpu_cost(usage),
                event_count=usage.event_count if usage else 0,
                detection_count=usage.total_images_processed if usage else 0,
            )
        )
    return history
