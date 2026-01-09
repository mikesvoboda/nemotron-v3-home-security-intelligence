"""Unit tests for CostTracker service (NEM-1673).

This module tests the LLM inference cost tracking and budget controls service.
Tests cover:
- Token usage tracking per LLM request
- GPU-time tracking per model inference
- Cost estimation based on cloud equivalents
- Budget controls with daily/monthly limits
- Prometheus metrics integration
- Redis persistence
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.cost_tracker import (
    BudgetStatus,
    CloudPricing,
    CostModel,
    CostTracker,
    DailyUsage,
    UsageRecord,
    get_cost_tracker,
    reset_cost_tracker,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the global CostTracker singleton before each test."""
    reset_cost_tracker()
    yield
    reset_cost_tracker()


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client."""
    mock_client = AsyncMock()
    mock_client.hset = AsyncMock(return_value=True)
    mock_client.hgetall = AsyncMock(return_value={})
    mock_client.expire = AsyncMock(return_value=True)
    mock_client.scan_iter = AsyncMock(return_value=iter([]))
    return mock_client


@pytest.fixture
def mock_metrics_service():
    """Create a mock metrics service."""
    with patch("backend.services.cost_tracker.get_metrics_service") as mock:
        metrics = MagicMock()
        mock.return_value = metrics
        yield metrics


@pytest.fixture
def cost_tracker(mock_metrics_service):
    """Create a CostTracker instance with mocked dependencies."""
    return CostTracker(
        redis_client=None,
        daily_budget_usd=10.0,
        monthly_budget_usd=100.0,
        warning_threshold=0.8,
    )


# =============================================================================
# CloudPricing Tests
# =============================================================================


class TestCloudPricing:
    """Tests for CloudPricing configuration."""

    def test_default_pricing_values(self):
        """Test default pricing configuration values."""
        pricing = CloudPricing()

        assert pricing.input_cost_per_1k_tokens == 0.003
        assert pricing.output_cost_per_1k_tokens == 0.006
        assert pricing.gpu_cost_per_second == 0.000139
        assert pricing.detection_cost_per_image == 0.00002
        assert pricing.enrichment_cost_per_operation == 0.00001

    def test_custom_pricing_values(self):
        """Test custom pricing configuration."""
        pricing = CloudPricing(
            input_cost_per_1k_tokens=0.01,
            output_cost_per_1k_tokens=0.02,
            gpu_cost_per_second=0.001,
        )

        assert pricing.input_cost_per_1k_tokens == 0.01
        assert pricing.output_cost_per_1k_tokens == 0.02
        assert pricing.gpu_cost_per_second == 0.001


class TestCostModel:
    """Tests for CostModel enum."""

    def test_cost_model_values(self):
        """Test CostModel enum values."""
        assert CostModel.NEMOTRON.value == "nemotron"
        assert CostModel.RTDETR.value == "rtdetr"
        assert CostModel.FLORENCE.value == "florence"
        assert CostModel.CLIP.value == "clip"
        assert CostModel.ENRICHMENT.value == "enrichment"


# =============================================================================
# CostTracker Initialization Tests
# =============================================================================


class TestCostTrackerInitialization:
    """Tests for CostTracker initialization."""

    def test_initialization_with_defaults(self, mock_metrics_service):
        """Test CostTracker initializes with default values."""
        tracker = CostTracker()

        assert tracker._daily_budget_usd == 0.0
        assert tracker._monthly_budget_usd == 0.0
        assert tracker._warning_threshold == 0.8
        assert tracker._redis is None

    def test_initialization_with_custom_values(self, mock_metrics_service):
        """Test CostTracker initializes with custom values."""
        tracker = CostTracker(
            daily_budget_usd=50.0,
            monthly_budget_usd=500.0,
            warning_threshold=0.9,
        )

        assert tracker._daily_budget_usd == 50.0
        assert tracker._monthly_budget_usd == 500.0
        assert tracker._warning_threshold == 0.9

    def test_initialization_with_custom_pricing(self, mock_metrics_service):
        """Test CostTracker initializes with custom pricing."""
        pricing = CloudPricing(input_cost_per_1k_tokens=0.01)
        tracker = CostTracker(pricing=pricing)

        assert tracker._pricing.input_cost_per_1k_tokens == 0.01


# =============================================================================
# LLM Usage Tracking Tests
# =============================================================================


class TestLLMUsageTracking:
    """Tests for LLM usage tracking."""

    def test_track_llm_usage_creates_record(self, cost_tracker, mock_metrics_service):
        """Test tracking LLM usage creates a usage record."""
        record = cost_tracker.track_llm_usage(
            input_tokens=1000,
            output_tokens=500,
            model="nemotron",
            duration_seconds=2.5,
            camera_id="front_door",
        )

        assert isinstance(record, UsageRecord)
        assert record.model == "nemotron"
        assert record.input_tokens == 1000
        assert record.output_tokens == 500
        assert record.gpu_seconds == 2.5
        assert record.camera_id == "front_door"
        assert record.estimated_cost_usd > 0

    def test_track_llm_usage_calculates_cost(self, cost_tracker, mock_metrics_service):
        """Test LLM usage cost calculation."""
        # Using default pricing:
        # input_cost = (1000/1000) * 0.003 = 0.003
        # output_cost = (500/1000) * 0.006 = 0.003
        # gpu_cost = 2.5 * 0.000139 = 0.0003475
        # total = 0.003 + 0.003 + 0.0003475 = 0.0063475

        record = cost_tracker.track_llm_usage(
            input_tokens=1000,
            output_tokens=500,
            model="nemotron",
            duration_seconds=2.5,
        )

        expected_cost = 0.003 + 0.003 + (2.5 * 0.000139)
        assert abs(record.estimated_cost_usd - expected_cost) < 0.0001

    def test_track_llm_usage_records_metrics(self, cost_tracker, mock_metrics_service):
        """Test LLM usage tracking records Prometheus metrics."""
        cost_tracker.track_llm_usage(
            input_tokens=1000,
            output_tokens=500,
            model="nemotron",
            duration_seconds=2.5,
            camera_id="front_door",
        )

        mock_metrics_service.record_gpu_seconds.assert_called_once_with("nemotron", 2.5)
        mock_metrics_service.record_estimated_cost.assert_called_once()
        mock_metrics_service.record_event_analysis_cost.assert_called_once()

    def test_track_llm_usage_updates_daily_aggregates(self, cost_tracker, mock_metrics_service):
        """Test LLM usage tracking updates daily aggregates."""
        cost_tracker.track_llm_usage(
            input_tokens=1000,
            output_tokens=500,
            model="nemotron",
            duration_seconds=2.5,
        )

        daily = cost_tracker.get_daily_usage()
        assert daily is not None
        assert daily.total_input_tokens == 1000
        assert daily.total_output_tokens == 500
        assert daily.total_gpu_seconds == 2.5


# =============================================================================
# Detection Usage Tracking Tests
# =============================================================================


class TestDetectionUsageTracking:
    """Tests for detection model usage tracking."""

    def test_track_detection_usage_creates_record(self, cost_tracker, mock_metrics_service):
        """Test tracking detection usage creates a usage record."""
        record = cost_tracker.track_detection_usage(
            model="rtdetr",
            duration_seconds=0.15,
            images_processed=1,
        )

        assert isinstance(record, UsageRecord)
        assert record.model == "rtdetr"
        assert record.gpu_seconds == 0.15
        assert record.images_processed == 1
        assert record.estimated_cost_usd > 0

    def test_track_detection_usage_calculates_cost(self, cost_tracker, mock_metrics_service):
        """Test detection usage cost calculation."""
        # gpu_cost = 0.15 * 0.000139 = 0.00002085
        # image_cost = 1 * 0.00002 = 0.00002
        # total = 0.00004085

        record = cost_tracker.track_detection_usage(
            model="rtdetr",
            duration_seconds=0.15,
            images_processed=1,
        )

        expected_cost = (0.15 * 0.000139) + 0.00002
        assert abs(record.estimated_cost_usd - expected_cost) < 0.00001


# =============================================================================
# Enrichment Usage Tracking Tests
# =============================================================================


class TestEnrichmentUsageTracking:
    """Tests for enrichment model usage tracking."""

    def test_track_enrichment_usage_creates_record(self, cost_tracker, mock_metrics_service):
        """Test tracking enrichment usage creates a usage record."""
        record = cost_tracker.track_enrichment_usage(
            model="florence",
            duration_seconds=0.5,
            operations=3,
        )

        assert isinstance(record, UsageRecord)
        assert record.model == "florence"
        assert record.gpu_seconds == 0.5
        assert record.operations == 3
        assert record.estimated_cost_usd > 0


# =============================================================================
# Cost Estimation Tests
# =============================================================================


class TestCostEstimation:
    """Tests for cost estimation."""

    def test_estimate_cost_tokens_only(self, cost_tracker, mock_metrics_service):
        """Test cost estimation with tokens only."""
        cost = cost_tracker.estimate_cost(
            input_tokens=1000,
            output_tokens=500,
        )

        expected = (1000 / 1000 * 0.003) + (500 / 1000 * 0.006)
        assert abs(cost - expected) < 0.0001

    def test_estimate_cost_gpu_seconds_only(self, cost_tracker, mock_metrics_service):
        """Test cost estimation with GPU seconds only."""
        cost = cost_tracker.estimate_cost(gpu_seconds=10.0)

        expected = 10.0 * 0.000139
        assert abs(cost - expected) < 0.0001

    def test_estimate_cost_combined(self, cost_tracker, mock_metrics_service):
        """Test cost estimation with multiple inputs."""
        cost = cost_tracker.estimate_cost(
            input_tokens=1000,
            output_tokens=500,
            gpu_seconds=5.0,
            images=10,
            operations=5,
        )

        expected = (
            (1000 / 1000 * 0.003)  # input tokens
            + (500 / 1000 * 0.006)  # output tokens
            + (5.0 * 0.000139)  # gpu seconds
            + (10 * 0.00002)  # images
            + (5 * 0.00001)  # operations
        )
        assert abs(cost - expected) < 0.0001


# =============================================================================
# Budget Tracking Tests
# =============================================================================


class TestBudgetTracking:
    """Tests for budget tracking and thresholds."""

    def test_budget_utilization_calculated(self, cost_tracker, mock_metrics_service):
        """Test budget utilization is calculated correctly."""
        # Track usage that should be ~5% of daily budget ($10)
        cost_tracker.track_llm_usage(
            input_tokens=10000,
            output_tokens=5000,
            model="nemotron",
            duration_seconds=10.0,
        )

        mock_metrics_service.set_budget_utilization.assert_called()

    def test_budget_warning_on_threshold(self, mock_metrics_service):
        """Test budget warning is logged when threshold reached."""
        tracker = CostTracker(
            daily_budget_usd=0.01,  # Very low budget
            warning_threshold=0.8,
        )

        with patch("backend.services.cost_tracker.logger") as mock_logger:
            # This should exceed 80% of $0.01 budget
            tracker.track_llm_usage(
                input_tokens=10000,
                output_tokens=5000,
                model="nemotron",
                duration_seconds=10.0,
            )

            # Should have logged a warning
            mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_get_budget_status(self, cost_tracker, mock_metrics_service):
        """Test getting budget status."""
        cost_tracker.track_llm_usage(
            input_tokens=1000,
            output_tokens=500,
            model="nemotron",
            duration_seconds=2.5,
        )

        status = await cost_tracker.get_budget_status()

        assert isinstance(status, BudgetStatus)
        assert status.daily_limit_usd == 10.0
        assert status.monthly_limit_usd == 100.0
        assert status.daily_used_usd > 0
        assert status.daily_remaining_usd < 10.0
        assert status.daily_utilization_ratio > 0
        assert not status.daily_exceeded
        assert not status.monthly_exceeded

    @pytest.mark.asyncio
    async def test_budget_exceeded_detection(self, mock_metrics_service):
        """Test detection of exceeded budget."""
        tracker = CostTracker(
            daily_budget_usd=0.001,  # Very low budget
            monthly_budget_usd=0.01,
        )

        # Track enough usage to exceed budget
        tracker.track_llm_usage(
            input_tokens=10000,
            output_tokens=5000,
            model="nemotron",
            duration_seconds=10.0,
        )

        status = await tracker.get_budget_status()

        assert status.daily_exceeded
        # Both daily and monthly exceed, check that both were called
        mock_metrics_service.record_budget_exceeded.assert_any_call("daily")


# =============================================================================
# Daily Usage Tests
# =============================================================================


class TestDailyUsage:
    """Tests for daily usage aggregation."""

    def test_get_daily_usage_returns_none_for_no_data(self, cost_tracker, mock_metrics_service):
        """Test get_daily_usage returns None when no data exists."""

        yesterday = datetime.now(UTC).date() - timedelta(days=1)
        usage = cost_tracker.get_daily_usage(yesterday)

        assert usage is None

    def test_get_daily_usage_returns_data(self, cost_tracker, mock_metrics_service):
        """Test get_daily_usage returns data for today."""
        cost_tracker.track_llm_usage(
            input_tokens=1000,
            output_tokens=500,
            model="nemotron",
            duration_seconds=2.5,
        )

        usage = cost_tracker.get_daily_usage()

        assert usage is not None
        assert isinstance(usage, DailyUsage)
        assert usage.date == datetime.now(UTC).date()

    def test_multiple_usages_aggregate(self, cost_tracker, mock_metrics_service):
        """Test multiple usage records aggregate correctly."""
        cost_tracker.track_llm_usage(
            input_tokens=1000,
            output_tokens=500,
            model="nemotron",
            duration_seconds=2.5,
        )
        cost_tracker.track_llm_usage(
            input_tokens=2000,
            output_tokens=1000,
            model="nemotron",
            duration_seconds=3.5,
        )

        usage = cost_tracker.get_daily_usage()

        assert usage.total_input_tokens == 3000
        assert usage.total_output_tokens == 1500
        assert usage.total_gpu_seconds == 6.0


# =============================================================================
# Monthly Usage Tests
# =============================================================================


class TestMonthlyUsage:
    """Tests for monthly usage aggregation."""

    def test_get_monthly_usage_empty(self, cost_tracker, mock_metrics_service):
        """Test get_monthly_usage returns empty list when no data."""
        usage = cost_tracker.get_monthly_usage()

        assert usage == []

    def test_get_monthly_usage_with_data(self, cost_tracker, mock_metrics_service):
        """Test get_monthly_usage returns data."""
        cost_tracker.track_llm_usage(
            input_tokens=1000,
            output_tokens=500,
            model="nemotron",
            duration_seconds=2.5,
        )

        usage = cost_tracker.get_monthly_usage()

        assert len(usage) == 1
        assert usage[0].date == datetime.now(UTC).date()


# =============================================================================
# Usage Summary Tests
# =============================================================================


class TestUsageSummary:
    """Tests for usage summary."""

    def test_get_usage_summary_empty(self, cost_tracker, mock_metrics_service):
        """Test get_usage_summary with no data."""
        summary = cost_tracker.get_usage_summary()

        assert summary["today"]["cost_usd"] == 0.0
        assert summary["this_month"]["cost_usd"] == 0.0
        assert summary["all_time"]["total_cost_usd"] == 0.0

    def test_get_usage_summary_with_data(self, cost_tracker, mock_metrics_service):
        """Test get_usage_summary with data."""
        cost_tracker.track_llm_usage(
            input_tokens=1000,
            output_tokens=500,
            model="nemotron",
            duration_seconds=2.5,
        )
        cost_tracker.increment_event_count()

        summary = cost_tracker.get_usage_summary()

        assert summary["today"]["cost_usd"] > 0
        assert summary["today"]["input_tokens"] == 1000
        assert summary["today"]["output_tokens"] == 500
        assert summary["today"]["events"] == 1
        assert summary["this_month"]["cost_usd"] > 0
        assert summary["budgets"]["daily_limit_usd"] == 10.0
        assert summary["budgets"]["monthly_limit_usd"] == 100.0


# =============================================================================
# Event Count Tests
# =============================================================================


class TestEventCount:
    """Tests for event count tracking."""

    def test_increment_event_count(self, cost_tracker, mock_metrics_service):
        """Test incrementing event count."""
        cost_tracker.increment_event_count()
        cost_tracker.increment_event_count(5)

        usage = cost_tracker.get_daily_usage()
        assert usage.event_count == 6


# =============================================================================
# Redis Persistence Tests
# =============================================================================


class TestRedisPersistence:
    """Tests for Redis persistence."""

    @pytest.mark.asyncio
    async def test_persist_usage(self, mock_redis_client, mock_metrics_service):
        """Test persisting usage to Redis."""
        tracker = CostTracker(redis_client=mock_redis_client)
        tracker.track_llm_usage(
            input_tokens=1000,
            output_tokens=500,
            model="nemotron",
            duration_seconds=2.5,
        )

        await tracker.persist_usage()

        mock_redis_client.hset.assert_called()
        mock_redis_client.expire.assert_called()

    @pytest.mark.asyncio
    async def test_load_usage(self, mock_redis_client, mock_metrics_service):
        """Test loading usage from Redis."""
        today = datetime.now(UTC).date()

        # Create an async generator for scan_iter
        async def async_scan_iter(*args, **kwargs):
            yield f"hsi:cost_tracking:daily:{today.isoformat()}".encode()

        mock_redis_client.scan_iter = async_scan_iter
        mock_redis_client.hgetall = AsyncMock(
            return_value={
                b"date": today.isoformat().encode(),
                b"total_input_tokens": b"1000",
                b"total_output_tokens": b"500",
                b"total_gpu_seconds": b"2.5",
                b"total_images_processed": b"0",
                b"total_enrichment_operations": b"0",
                b"total_estimated_cost_usd": b"0.01",
                b"event_count": b"1",
            }
        )

        tracker = CostTracker(redis_client=mock_redis_client)
        await tracker.load_usage()

        usage = tracker.get_daily_usage()
        assert usage is not None
        assert usage.total_input_tokens == 1000


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_cost_tracker_returns_singleton(self, mock_metrics_service):
        """Test get_cost_tracker returns same instance."""
        tracker1 = get_cost_tracker()
        tracker2 = get_cost_tracker()

        assert tracker1 is tracker2

    def test_reset_cost_tracker_clears_singleton(self, mock_metrics_service):
        """Test reset_cost_tracker clears the singleton."""
        tracker1 = get_cost_tracker()
        reset_cost_tracker()
        tracker2 = get_cost_tracker()

        assert tracker1 is not tracker2


# =============================================================================
# Model-specific Usage Tests
# =============================================================================


class TestModelSpecificUsage:
    """Tests for tracking usage by model."""

    def test_usage_by_model_tracking(self, cost_tracker, mock_metrics_service):
        """Test usage is tracked per model."""
        cost_tracker.track_llm_usage(
            input_tokens=1000,
            output_tokens=500,
            model="nemotron",
            duration_seconds=2.5,
        )
        cost_tracker.track_detection_usage(
            model="rtdetr",
            duration_seconds=0.15,
            images_processed=1,
        )

        usage = cost_tracker.get_daily_usage()

        assert "nemotron" in usage.usage_by_model
        assert "rtdetr" in usage.usage_by_model
        assert usage.usage_by_model["nemotron"] > 0
        assert usage.usage_by_model["rtdetr"] > 0


# =============================================================================
# Edge Cases Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_zero_tokens(self, cost_tracker, mock_metrics_service):
        """Test handling zero tokens."""
        record = cost_tracker.track_llm_usage(
            input_tokens=0,
            output_tokens=0,
            model="nemotron",
            duration_seconds=0.0,
        )

        assert record.estimated_cost_usd == 0.0

    def test_negative_values_treated_as_zero(self, cost_tracker, mock_metrics_service):
        """Test that negative values don't produce negative costs."""
        # GPU seconds of 0 or negative should not add cost
        record = cost_tracker.track_llm_usage(
            input_tokens=0,
            output_tokens=0,
            model="nemotron",
            duration_seconds=0.0,
        )

        assert record.estimated_cost_usd >= 0

    def test_very_large_values(self, cost_tracker, mock_metrics_service):
        """Test handling very large token counts."""
        record = cost_tracker.track_llm_usage(
            input_tokens=1_000_000,
            output_tokens=500_000,
            model="nemotron",
            duration_seconds=100.0,
        )

        # Should calculate without overflow
        assert record.estimated_cost_usd > 0
        assert isinstance(record.estimated_cost_usd, float)
