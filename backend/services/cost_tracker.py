"""LLM Inference Cost Tracking and Budget Controls (NEM-1673).

This module provides cost tracking for AI inference operations including:
- Token usage tracking per LLM request (input/output)
- GPU-time tracking per model inference
- Cost estimation based on cloud equivalents
- Budget controls with daily/monthly limits and alerts
- Prometheus metrics for monitoring

Cloud equivalent pricing is used to estimate what the inference would cost
if running on cloud GPU instances (e.g., AWS/GCP/Azure GPU instances).

Example usage:
    from backend.services.cost_tracker import get_cost_tracker

    tracker = get_cost_tracker()

    # Track LLM usage
    tracker.track_llm_usage(
        input_tokens=1500,
        output_tokens=500,
        model="nemotron",
        duration_seconds=2.5,
        camera_id="front_door"
    )

    # Track detection model usage
    tracker.track_detection_usage(
        model="yolo26",
        duration_seconds=0.15,
        images_processed=1
    )

    # Check budget status
    status = await tracker.get_budget_status()
    if status.daily_exceeded:
        logger.warning("Daily budget exceeded!")
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from backend.core.metrics import get_metrics_service

if TYPE_CHECKING:
    from redis.asyncio import Redis


logger = logging.getLogger(__name__)


class CostModel(str, Enum):
    """Supported cost models for inference pricing."""

    NEMOTRON = "nemotron"
    YOLO26 = "yolo26"
    FLORENCE = "florence"
    CLIP = "clip"
    ENRICHMENT = "enrichment"


@dataclass(frozen=True)
class CloudPricing:
    """Cloud equivalent pricing for cost estimation.

    Prices are based on approximate cloud GPU instance costs and model performance.
    These are estimates for capacity planning, not actual billing.

    Pricing model:
    - LLM tokens: Based on API pricing for similar models (input/output)
    - GPU seconds: Based on hourly GPU instance costs converted to per-second
    - Detection: Fixed cost per image processed

    Reference pricing (approximate):
    - NVIDIA A5500 equivalent: ~$0.50/hour = ~$0.000139/second
    - LLM tokens (similar to GPT-4): $0.03/1K input, $0.06/1K output (scaled down for local)
    - For local deployment, we use 10% of cloud prices as equivalent estimate
    """

    # Token pricing per 1000 tokens (USD)
    # Using ~10% of cloud API prices for local equivalent
    input_cost_per_1k_tokens: float = 0.003  # $0.003/1K input tokens
    output_cost_per_1k_tokens: float = 0.006  # $0.006/1K output tokens

    # GPU second pricing (USD per second)
    # Based on A5500 equivalent instance at ~$0.50/hour
    gpu_cost_per_second: float = 0.000139

    # Detection model pricing (USD per image)
    # Based on GPU time per image (~0.15s average)
    detection_cost_per_image: float = 0.00002

    # Enrichment model pricing (USD per operation)
    enrichment_cost_per_operation: float = 0.00001


# Default pricing configuration
DEFAULT_PRICING = CloudPricing()


@dataclass
class UsageRecord:
    """Record of a single inference usage."""

    timestamp: datetime
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    gpu_seconds: float = 0.0
    images_processed: int = 0
    operations: int = 0
    estimated_cost_usd: float = 0.0
    camera_id: str | None = None


@dataclass
class DailyUsage:
    """Aggregated usage for a single day."""

    date: date
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_gpu_seconds: float = 0.0
    total_images_processed: int = 0
    total_enrichment_operations: int = 0
    total_estimated_cost_usd: float = 0.0
    event_count: int = 0
    usage_by_model: dict[str, float] = field(default_factory=dict)


@dataclass
class BudgetStatus:
    """Current budget status and utilization."""

    daily_limit_usd: float
    monthly_limit_usd: float
    daily_used_usd: float
    monthly_used_usd: float
    daily_remaining_usd: float
    monthly_remaining_usd: float
    daily_utilization_ratio: float
    monthly_utilization_ratio: float
    daily_exceeded: bool
    monthly_exceeded: bool
    warning_threshold_reached: bool


class CostTracker:
    """LLM Inference Cost Tracking and Budget Controls.

    Tracks token usage, GPU time, and estimated costs for AI inference operations.
    Provides budget controls with configurable daily/monthly limits and alerts.

    Attributes:
        pricing: Cloud equivalent pricing configuration
        daily_budget_usd: Maximum daily budget in USD (0 = unlimited)
        monthly_budget_usd: Maximum monthly budget in USD (0 = unlimited)
        warning_threshold: Ratio at which to trigger budget warnings (0.0-1.0)
    """

    def __init__(
        self,
        redis_client: Redis | None = None,
        pricing: CloudPricing | None = None,
        daily_budget_usd: float = 0.0,
        monthly_budget_usd: float = 0.0,
        warning_threshold: float = 0.8,
    ) -> None:
        """Initialize the cost tracker.

        Args:
            redis_client: Optional Redis client for persisting usage data
            pricing: Cloud equivalent pricing configuration (uses defaults if None)
            daily_budget_usd: Maximum daily budget in USD (0 = unlimited)
            monthly_budget_usd: Maximum monthly budget in USD (0 = unlimited)
            warning_threshold: Ratio at which to trigger budget warnings (0.0-1.0)
        """
        self._redis = redis_client
        self._pricing = pricing or DEFAULT_PRICING
        self._daily_budget_usd = daily_budget_usd
        self._monthly_budget_usd = monthly_budget_usd
        self._warning_threshold = warning_threshold
        self._metrics = get_metrics_service()

        # In-memory usage tracking (per day)
        self._daily_usage: dict[date, DailyUsage] = {}
        self._lock = asyncio.Lock()

        # Redis key prefixes
        self._redis_prefix = "hsi:cost_tracking"

    def track_llm_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str,
        duration_seconds: float,
        camera_id: str | None = None,
    ) -> UsageRecord:
        """Track LLM inference usage.

        Args:
            input_tokens: Number of input/prompt tokens
            output_tokens: Number of output/completion tokens
            model: Model identifier (e.g., 'nemotron')
            duration_seconds: Inference duration in seconds
            camera_id: Optional camera identifier

        Returns:
            UsageRecord with calculated cost estimate
        """
        # Calculate token cost
        token_cost = (input_tokens / 1000.0) * self._pricing.input_cost_per_1k_tokens + (
            output_tokens / 1000.0
        ) * self._pricing.output_cost_per_1k_tokens

        # Calculate GPU time cost
        gpu_cost = duration_seconds * self._pricing.gpu_cost_per_second

        # Total estimated cost
        total_cost = token_cost + gpu_cost

        # Create usage record
        record = UsageRecord(
            timestamp=datetime.now(UTC),
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            gpu_seconds=duration_seconds,
            estimated_cost_usd=total_cost,
            camera_id=camera_id,
        )

        # Record metrics
        self._metrics.record_gpu_seconds(model, duration_seconds)
        self._metrics.record_estimated_cost(model, total_cost)
        if camera_id:
            self._metrics.record_event_analysis_cost(camera_id, total_cost)

        # Update daily aggregates
        self._update_daily_usage(record)

        logger.debug(
            f"Tracked LLM usage: model={model}, input_tokens={input_tokens}, "
            f"output_tokens={output_tokens}, duration={duration_seconds:.3f}s, "
            f"cost=${total_cost:.6f}"
        )

        return record

    def track_detection_usage(
        self,
        model: str,
        duration_seconds: float,
        images_processed: int = 1,
    ) -> UsageRecord:
        """Track detection model usage.

        Args:
            model: Model identifier (e.g., 'yolo26', 'florence')
            duration_seconds: Inference duration in seconds
            images_processed: Number of images processed

        Returns:
            UsageRecord with calculated cost estimate
        """
        # Calculate GPU time cost
        gpu_cost = duration_seconds * self._pricing.gpu_cost_per_second

        # Calculate per-image cost
        image_cost = images_processed * self._pricing.detection_cost_per_image

        # Total estimated cost
        total_cost = gpu_cost + image_cost

        # Create usage record
        record = UsageRecord(
            timestamp=datetime.now(UTC),
            model=model,
            gpu_seconds=duration_seconds,
            images_processed=images_processed,
            estimated_cost_usd=total_cost,
        )

        # Record metrics
        self._metrics.record_gpu_seconds(model, duration_seconds)
        self._metrics.record_estimated_cost(model, total_cost)

        # Update daily aggregates
        self._update_daily_usage(record)

        logger.debug(
            f"Tracked detection usage: model={model}, images={images_processed}, "
            f"duration={duration_seconds:.3f}s, cost=${total_cost:.6f}"
        )

        return record

    def track_enrichment_usage(
        self,
        model: str,
        duration_seconds: float,
        operations: int = 1,
    ) -> UsageRecord:
        """Track enrichment model usage (CLIP, Florence, etc.).

        Args:
            model: Model identifier (e.g., 'clip', 'florence', 'enrichment')
            duration_seconds: Inference duration in seconds
            operations: Number of enrichment operations performed

        Returns:
            UsageRecord with calculated cost estimate
        """
        # Calculate GPU time cost
        gpu_cost = duration_seconds * self._pricing.gpu_cost_per_second

        # Calculate per-operation cost
        operation_cost = operations * self._pricing.enrichment_cost_per_operation

        # Total estimated cost
        total_cost = gpu_cost + operation_cost

        # Create usage record
        record = UsageRecord(
            timestamp=datetime.now(UTC),
            model=model,
            gpu_seconds=duration_seconds,
            operations=operations,
            estimated_cost_usd=total_cost,
        )

        # Record metrics
        self._metrics.record_gpu_seconds(model, duration_seconds)
        self._metrics.record_estimated_cost(model, total_cost)

        # Update daily aggregates
        self._update_daily_usage(record)

        logger.debug(
            f"Tracked enrichment usage: model={model}, operations={operations}, "
            f"duration={duration_seconds:.3f}s, cost=${total_cost:.6f}"
        )

        return record

    def estimate_cost(
        self,
        input_tokens: int = 0,
        output_tokens: int = 0,
        gpu_seconds: float = 0.0,
        images: int = 0,
        operations: int = 0,
    ) -> float:
        """Estimate cost for a hypothetical operation.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            gpu_seconds: GPU time in seconds
            images: Number of images to process
            operations: Number of enrichment operations

        Returns:
            Estimated cost in USD
        """
        cost = 0.0

        # Token costs
        if input_tokens > 0:
            cost += (input_tokens / 1000.0) * self._pricing.input_cost_per_1k_tokens
        if output_tokens > 0:
            cost += (output_tokens / 1000.0) * self._pricing.output_cost_per_1k_tokens

        # GPU time cost
        if gpu_seconds > 0:
            cost += gpu_seconds * self._pricing.gpu_cost_per_second

        # Detection cost
        if images > 0:
            cost += images * self._pricing.detection_cost_per_image

        # Enrichment cost
        if operations > 0:
            cost += operations * self._pricing.enrichment_cost_per_operation

        return cost

    def _update_daily_usage(self, record: UsageRecord) -> None:
        """Update daily usage aggregates.

        Args:
            record: Usage record to add to daily totals
        """
        today = record.timestamp.date()

        if today not in self._daily_usage:
            self._daily_usage[today] = DailyUsage(date=today)

        usage = self._daily_usage[today]
        usage.total_input_tokens += record.input_tokens
        usage.total_output_tokens += record.output_tokens
        usage.total_gpu_seconds += record.gpu_seconds
        usage.total_images_processed += record.images_processed
        usage.total_enrichment_operations += record.operations
        usage.total_estimated_cost_usd += record.estimated_cost_usd

        # Track per-model costs
        if record.model not in usage.usage_by_model:
            usage.usage_by_model[record.model] = 0.0
        usage.usage_by_model[record.model] += record.estimated_cost_usd

        # Update Prometheus gauges
        self._metrics.set_daily_cost(usage.total_estimated_cost_usd)

        # Calculate monthly total
        current_month = today.month
        current_year = today.year
        monthly_total = sum(
            u.total_estimated_cost_usd
            for d, u in self._daily_usage.items()
            if d.month == current_month and d.year == current_year
        )
        self._metrics.set_monthly_cost(monthly_total)

        # Calculate and update cost efficiency metrics (all-time averages)
        total_cost = sum(u.total_estimated_cost_usd for u in self._daily_usage.values())
        total_detections = sum(u.total_images_processed for u in self._daily_usage.values())
        total_events = sum(u.event_count for u in self._daily_usage.values())

        if total_detections > 0:
            self._metrics.set_cost_per_detection(total_cost / total_detections)
        if total_events > 0:
            self._metrics.set_cost_per_event(total_cost / total_events)

        # Check budget thresholds
        self._check_budget_thresholds(usage.total_estimated_cost_usd, monthly_total)

    def _check_budget_thresholds(self, daily_cost: float, monthly_cost: float) -> None:
        """Check and update budget threshold metrics.

        Args:
            daily_cost: Current daily cost
            monthly_cost: Current monthly cost
        """
        # Daily budget check
        if self._daily_budget_usd > 0:
            daily_ratio = daily_cost / self._daily_budget_usd
            self._metrics.set_budget_utilization("daily", daily_ratio)

            if daily_ratio >= 1.0:
                self._metrics.record_budget_exceeded("daily")
                logger.warning(
                    f"Daily budget exceeded: ${daily_cost:.4f} / ${self._daily_budget_usd:.2f}"
                )
            elif daily_ratio >= self._warning_threshold:
                logger.warning(
                    f"Daily budget warning ({self._warning_threshold:.0%}): "
                    f"${daily_cost:.4f} / ${self._daily_budget_usd:.2f}"
                )

        # Monthly budget check
        if self._monthly_budget_usd > 0:
            monthly_ratio = monthly_cost / self._monthly_budget_usd
            self._metrics.set_budget_utilization("monthly", monthly_ratio)

            if monthly_ratio >= 1.0:
                self._metrics.record_budget_exceeded("monthly")
                logger.warning(
                    f"Monthly budget exceeded: ${monthly_cost:.4f} / ${self._monthly_budget_usd:.2f}"
                )
            elif monthly_ratio >= self._warning_threshold:
                logger.warning(
                    f"Monthly budget warning ({self._warning_threshold:.0%}): "
                    f"${monthly_cost:.4f} / ${self._monthly_budget_usd:.2f}"
                )

    def get_daily_usage(self, target_date: date | None = None) -> DailyUsage | None:
        """Get usage for a specific day.

        Args:
            target_date: Date to query (defaults to today)

        Returns:
            DailyUsage for the date, or None if no data
        """
        if target_date is None:
            target_date = datetime.now(UTC).date()
        return self._daily_usage.get(target_date)

    def get_monthly_usage(
        self,
        year: int | None = None,
        month: int | None = None,
    ) -> list[DailyUsage]:
        """Get usage for a specific month.

        Args:
            year: Year to query (defaults to current year)
            month: Month to query (defaults to current month)

        Returns:
            List of DailyUsage records for the month
        """
        now = datetime.now(UTC)
        if year is None:
            year = now.year
        if month is None:
            month = now.month

        return [
            u for d, u in sorted(self._daily_usage.items()) if d.year == year and d.month == month
        ]

    async def get_budget_status(self) -> BudgetStatus:
        """Get current budget status.

        Returns:
            BudgetStatus with utilization and remaining amounts
        """
        now = datetime.now(UTC)
        today = now.date()

        # Get daily usage
        daily_usage = self._daily_usage.get(today)
        daily_used = daily_usage.total_estimated_cost_usd if daily_usage else 0.0

        # Get monthly usage
        monthly_used = sum(
            u.total_estimated_cost_usd
            for d, u in self._daily_usage.items()
            if d.year == today.year and d.month == today.month
        )

        # Calculate remaining and ratios
        daily_remaining = max(0.0, self._daily_budget_usd - daily_used)
        monthly_remaining = max(0.0, self._monthly_budget_usd - monthly_used)

        daily_ratio = daily_used / self._daily_budget_usd if self._daily_budget_usd > 0 else 0.0
        monthly_ratio = (
            monthly_used / self._monthly_budget_usd if self._monthly_budget_usd > 0 else 0.0
        )

        daily_exceeded = daily_ratio >= 1.0 if self._daily_budget_usd > 0 else False
        monthly_exceeded = monthly_ratio >= 1.0 if self._monthly_budget_usd > 0 else False

        warning_reached = (
            daily_ratio >= self._warning_threshold or monthly_ratio >= self._warning_threshold
        )

        return BudgetStatus(
            daily_limit_usd=self._daily_budget_usd,
            monthly_limit_usd=self._monthly_budget_usd,
            daily_used_usd=daily_used,
            monthly_used_usd=monthly_used,
            daily_remaining_usd=daily_remaining,
            monthly_remaining_usd=monthly_remaining,
            daily_utilization_ratio=daily_ratio,
            monthly_utilization_ratio=monthly_ratio,
            daily_exceeded=daily_exceeded,
            monthly_exceeded=monthly_exceeded,
            warning_threshold_reached=warning_reached,
        )

    async def persist_usage(self) -> None:
        """Persist usage data to Redis.

        This is called periodically to ensure usage data survives restarts.
        """
        if self._redis is None:
            return

        try:
            async with self._lock:
                for usage_date, usage in self._daily_usage.items():
                    key = f"{self._redis_prefix}:daily:{usage_date.isoformat()}"
                    data = {
                        "date": usage_date.isoformat(),
                        "total_input_tokens": usage.total_input_tokens,
                        "total_output_tokens": usage.total_output_tokens,
                        "total_gpu_seconds": usage.total_gpu_seconds,
                        "total_images_processed": usage.total_images_processed,
                        "total_enrichment_operations": usage.total_enrichment_operations,
                        "total_estimated_cost_usd": usage.total_estimated_cost_usd,
                        "event_count": usage.event_count,
                    }
                    await self._redis.hset(key, mapping=data)  # type: ignore[misc]
                    # Set TTL for 90 days
                    await self._redis.expire(key, 90 * 24 * 60 * 60)  # type: ignore[misc]

            logger.debug(f"Persisted usage data for {len(self._daily_usage)} days")
        except Exception as e:
            logger.error(f"Failed to persist usage data: {e}")

    async def load_usage(self) -> None:
        """Load usage data from Redis.

        This is called on startup to restore usage data.
        """
        if self._redis is None:
            return

        try:
            async with self._lock:
                # Find all daily usage keys
                pattern = f"{self._redis_prefix}:daily:*"
                keys: list[bytes] = []
                async for key in self._redis.scan_iter(match=pattern):
                    keys.append(key)

                for key in keys:
                    # Decode key to string for hgetall
                    key_str = key.decode() if isinstance(key, bytes) else str(key)
                    data = await self._redis.hgetall(key_str)  # type: ignore[misc]
                    if not data:
                        continue

                    # Decode bytes to str
                    decoded: dict[str, Any] = {}
                    for k, v in data.items():
                        k_str = k.decode() if isinstance(k, bytes) else k
                        v_str = v.decode() if isinstance(v, bytes) else v
                        decoded[k_str] = v_str

                    usage_date = date.fromisoformat(decoded["date"])
                    usage = DailyUsage(
                        date=usage_date,
                        total_input_tokens=int(decoded.get("total_input_tokens", 0)),
                        total_output_tokens=int(decoded.get("total_output_tokens", 0)),
                        total_gpu_seconds=float(decoded.get("total_gpu_seconds", 0.0)),
                        total_images_processed=int(decoded.get("total_images_processed", 0)),
                        total_enrichment_operations=int(
                            decoded.get("total_enrichment_operations", 0)
                        ),
                        total_estimated_cost_usd=float(
                            decoded.get("total_estimated_cost_usd", 0.0)
                        ),
                        event_count=int(decoded.get("event_count", 0)),
                    )
                    self._daily_usage[usage_date] = usage

            logger.info(f"Loaded usage data for {len(self._daily_usage)} days from Redis")
        except Exception as e:
            logger.error(f"Failed to load usage data: {e}")

    def get_usage_summary(self) -> dict[str, Any]:
        """Get a summary of usage statistics.

        Returns:
            Dictionary with usage summary
        """
        now = datetime.now(UTC)
        today = now.date()

        # Today's usage
        today_usage = self._daily_usage.get(today)

        # This month's usage
        month_usage = self.get_monthly_usage()
        monthly_cost = sum(u.total_estimated_cost_usd for u in month_usage)
        monthly_tokens = sum(u.total_input_tokens + u.total_output_tokens for u in month_usage)
        monthly_gpu_seconds = sum(u.total_gpu_seconds for u in month_usage)

        # Average cost per event (if we have data)
        total_events = sum(u.event_count for u in self._daily_usage.values())
        total_cost = sum(u.total_estimated_cost_usd for u in self._daily_usage.values())
        avg_cost_per_event = total_cost / total_events if total_events > 0 else 0.0

        return {
            "today": {
                "cost_usd": today_usage.total_estimated_cost_usd if today_usage else 0.0,
                "input_tokens": today_usage.total_input_tokens if today_usage else 0,
                "output_tokens": today_usage.total_output_tokens if today_usage else 0,
                "gpu_seconds": today_usage.total_gpu_seconds if today_usage else 0.0,
                "events": today_usage.event_count if today_usage else 0,
            },
            "this_month": {
                "cost_usd": monthly_cost,
                "total_tokens": monthly_tokens,
                "gpu_seconds": monthly_gpu_seconds,
                "days_tracked": len(month_usage),
            },
            "all_time": {
                "total_cost_usd": total_cost,
                "total_events": total_events,
                "avg_cost_per_event_usd": avg_cost_per_event,
                "days_tracked": len(self._daily_usage),
            },
            "budgets": {
                "daily_limit_usd": self._daily_budget_usd,
                "monthly_limit_usd": self._monthly_budget_usd,
                "warning_threshold": self._warning_threshold,
            },
            "pricing": {
                "input_cost_per_1k_tokens": self._pricing.input_cost_per_1k_tokens,
                "output_cost_per_1k_tokens": self._pricing.output_cost_per_1k_tokens,
                "gpu_cost_per_second": self._pricing.gpu_cost_per_second,
            },
        }

    def increment_event_count(self, count: int = 1) -> None:
        """Increment the event count for today.

        Args:
            count: Number of events to add
        """
        today = datetime.now(UTC).date()
        if today not in self._daily_usage:
            self._daily_usage[today] = DailyUsage(date=today)
        self._daily_usage[today].event_count += count

        # Update cost per event metric
        total_cost = sum(u.total_estimated_cost_usd for u in self._daily_usage.values())
        total_events = sum(u.event_count for u in self._daily_usage.values())
        if total_events > 0:
            self._metrics.set_cost_per_event(total_cost / total_events)


# Global singleton instance
_cost_tracker: CostTracker | None = None


def get_cost_tracker(
    redis_client: Redis | None = None,
    pricing: CloudPricing | None = None,
    daily_budget_usd: float = 0.0,
    monthly_budget_usd: float = 0.0,
    warning_threshold: float = 0.8,
) -> CostTracker:
    """Get the global CostTracker instance.

    On first call, creates a new instance with the provided configuration.
    Subsequent calls return the existing instance (ignoring new parameters).

    Args:
        redis_client: Optional Redis client for persistence
        pricing: Cloud equivalent pricing configuration
        daily_budget_usd: Maximum daily budget in USD
        monthly_budget_usd: Maximum monthly budget in USD
        warning_threshold: Ratio at which to trigger budget warnings

    Returns:
        The singleton CostTracker instance
    """
    global _cost_tracker  # noqa: PLW0603
    if _cost_tracker is None:
        _cost_tracker = CostTracker(
            redis_client=redis_client,
            pricing=pricing,
            daily_budget_usd=daily_budget_usd,
            monthly_budget_usd=monthly_budget_usd,
            warning_threshold=warning_threshold,
        )
    return _cost_tracker


def reset_cost_tracker() -> None:
    """Reset the global CostTracker instance.

    Used for testing to ensure clean state between tests.
    """
    global _cost_tracker  # noqa: PLW0603
    _cost_tracker = None
