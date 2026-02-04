"""Trend calculation service for sparkline visualizations.

This service provides time-bucketed event metrics with rolling 24-hour
baseline comparisons for dashboard sparkline displays.

Features:
- Time bucket aggregation (5-min for hourly, 1-hour for daily)
- Rolling 24-hour baseline calculations
- Deviation percentage calculations
- Handles edge cases (no data, null risk scores, etc.)

Example:
    service = TrendService(db_session)
    trends = await service.get_trend_data("hourly")
    # Returns: {"event_count": {...}, "avg_risk": {...}, "high_risk_count": {...}}
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, TypedDict

from backend.core.logging import get_logger
from backend.repositories.event_repository import EventRepository


class BucketData(TypedDict):
    """Type definition for bucket aggregation data."""

    count: int
    total_risk: float
    risk_scores: list[float]
    high_risk_count: int


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

# High-risk threshold (events with risk_score >= this are considered high-risk)
HIGH_RISK_THRESHOLD = 70

# Time bucket configurations
HOURLY_BUCKET_SIZE = timedelta(minutes=5)
HOURLY_NUM_BUCKETS = 12  # 12 x 5-min = 1 hour

DAILY_BUCKET_SIZE = timedelta(hours=1)
DAILY_NUM_BUCKETS = 24  # 24 x 1-hour = 24 hours

# Baseline calculation window (rolling 24-hour average)
BASELINE_WINDOW = timedelta(hours=24)


def _calculate_deviation(current: float, baseline: float) -> float:
    """Calculate percentage deviation from baseline.

    Args:
        current: Current value to compare
        baseline: Baseline value for comparison

    Returns:
        Percentage deviation (positive = above baseline, negative = below)
        Returns 0.0 if baseline is 0 to avoid division by zero.
    """
    if baseline == 0.0:
        return 0.0
    return round(((current - baseline) / baseline) * 100, 1)


def _aggregate_into_buckets(
    events: list[Any],
    end_time: datetime,
    bucket_size: timedelta,
    num_buckets: int,
) -> list[BucketData]:
    """Aggregate events into time buckets.

    Args:
        events: List of events with started_at and risk_score attributes
        end_time: End time for the time window (most recent bucket ends here)
        bucket_size: Duration of each bucket
        num_buckets: Number of buckets to create

    Returns:
        List of bucket dictionaries with count, total_risk, and high_risk_count
    """
    # Initialize buckets
    buckets: list[BucketData] = []
    for _ in range(num_buckets):
        buckets.append(
            {
                "count": 0,
                "total_risk": 0.0,
                "risk_scores": [],  # For average calculation
                "high_risk_count": 0,
            }
        )

    # Aggregate events into buckets
    for event in events:
        if event.started_at is None:
            continue

        # Calculate which bucket this event belongs to
        time_ago = end_time - event.started_at
        bucket_index = int(time_ago / bucket_size)

        if 0 <= bucket_index < num_buckets:
            buckets[bucket_index]["count"] += 1

            if event.risk_score is not None:
                buckets[bucket_index]["total_risk"] += event.risk_score
                buckets[bucket_index]["risk_scores"].append(event.risk_score)

                if event.risk_score >= HIGH_RISK_THRESHOLD:
                    buckets[bucket_index]["high_risk_count"] += 1

    return buckets


def _calculate_metrics_from_buckets(
    buckets: list[BucketData],
) -> dict[str, list[float]]:
    """Calculate metric arrays from bucket data.

    Args:
        buckets: List of bucket dictionaries from _aggregate_into_buckets

    Returns:
        Dictionary with event_counts, avg_risks, and high_risk_counts arrays
    """
    event_counts = []
    avg_risks = []
    high_risk_counts = []

    for bucket in buckets:
        event_counts.append(float(bucket["count"]))

        # Calculate average risk for this bucket
        if bucket["risk_scores"]:
            avg_risk = sum(bucket["risk_scores"]) / len(bucket["risk_scores"])
        else:
            avg_risk = 0.0
        avg_risks.append(round(avg_risk, 1))

        high_risk_counts.append(float(bucket["high_risk_count"]))

    return {
        "event_counts": event_counts,
        "avg_risks": avg_risks,
        "high_risk_counts": high_risk_counts,
    }


class TrendService:
    """Service for calculating trend data for sparkline visualizations.

    Provides time-bucketed metrics with rolling 24-hour baseline comparisons:
    - event_count: Number of events per bucket
    - avg_risk: Average risk score per bucket
    - high_risk_count: Number of high-risk events (>= 70) per bucket

    Example:
        service = TrendService(db_session)
        trends = await service.get_trend_data("hourly")
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the trend service.

        Args:
            db: SQLAlchemy async session for database queries
        """
        self.db = db
        self.repo = EventRepository(db)

    async def get_trend_data(self, trend_type: str) -> dict[str, Any]:
        """Get trend data for sparkline visualization.

        Args:
            trend_type: Either "hourly" (5-min buckets) or "daily" (1-hour buckets)

        Returns:
            Dictionary with event_count, avg_risk, and high_risk_count metrics,
            each containing values array, baseline, and deviation_pct.
        """
        now = datetime.now(UTC)

        # Determine bucket configuration based on trend type
        if trend_type == "daily":
            bucket_size = DAILY_BUCKET_SIZE
            num_buckets = DAILY_NUM_BUCKETS
            current_window = timedelta(hours=24)
        else:  # Default to hourly
            bucket_size = HOURLY_BUCKET_SIZE
            num_buckets = HOURLY_NUM_BUCKETS
            current_window = timedelta(hours=1)

        # Fetch events for current window and baseline window
        # Current window: most recent data for sparkline
        current_start = now - current_window
        # Baseline window: 24 hours before current window
        baseline_start = now - BASELINE_WINDOW - current_window
        baseline_end = now - current_window

        try:
            # Fetch current window events
            current_events = await self.repo.get_in_date_range(current_start, now)

            # Fetch baseline window events
            baseline_events = await self.repo.get_in_date_range(baseline_start, baseline_end)

            # Aggregate current events into buckets
            current_buckets = _aggregate_into_buckets(
                list(current_events), now, bucket_size, num_buckets
            )

            # Calculate metrics from buckets
            current_metrics = _calculate_metrics_from_buckets(current_buckets)

            # Calculate current totals for deviation
            current_event_total = sum(current_metrics["event_counts"])
            current_risk_total = sum(current_metrics["avg_risks"])
            current_high_risk_total = sum(current_metrics["high_risk_counts"])

            # Calculate current averages
            current_avg_events = current_event_total / num_buckets if num_buckets > 0 else 0
            current_avg_risk = current_risk_total / num_buckets if num_buckets > 0 else 0
            current_avg_high_risk = current_high_risk_total / num_buckets if num_buckets > 0 else 0

            # Calculate baseline metrics
            baseline_buckets = _aggregate_into_buckets(
                list(baseline_events), baseline_end, bucket_size, num_buckets
            )
            baseline_metrics = _calculate_metrics_from_buckets(baseline_buckets)

            baseline_event_total = sum(baseline_metrics["event_counts"])
            baseline_risk_total = sum(baseline_metrics["avg_risks"])
            baseline_high_risk_total = sum(baseline_metrics["high_risk_counts"])

            # Calculate baseline averages
            baseline_avg_events = baseline_event_total / num_buckets if num_buckets > 0 else 0
            baseline_avg_risk = baseline_risk_total / num_buckets if num_buckets > 0 else 0
            baseline_avg_high_risk = (
                baseline_high_risk_total / num_buckets if num_buckets > 0 else 0
            )

            # Build response
            return {
                "event_count": {
                    "values": current_metrics["event_counts"],
                    "baseline": round(baseline_avg_events, 1),
                    "deviation_pct": _calculate_deviation(current_avg_events, baseline_avg_events),
                },
                "avg_risk": {
                    "values": current_metrics["avg_risks"],
                    "baseline": round(baseline_avg_risk, 1),
                    "deviation_pct": _calculate_deviation(current_avg_risk, baseline_avg_risk),
                },
                "high_risk_count": {
                    "values": current_metrics["high_risk_counts"],
                    "baseline": round(baseline_avg_high_risk, 1),
                    "deviation_pct": _calculate_deviation(
                        current_avg_high_risk, baseline_avg_high_risk
                    ),
                },
            }

        except Exception as e:
            logger.error(f"Error calculating trend data: {e}")
            # Return empty trend data on error
            empty_values = [0.0] * num_buckets
            return {
                "event_count": {
                    "values": empty_values,
                    "baseline": 0.0,
                    "deviation_pct": 0.0,
                },
                "avg_risk": {
                    "values": empty_values,
                    "baseline": 0.0,
                    "deviation_pct": 0.0,
                },
                "high_risk_count": {
                    "values": empty_values,
                    "baseline": 0.0,
                    "deviation_pct": 0.0,
                },
            }
