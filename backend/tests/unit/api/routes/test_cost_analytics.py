"""Unit tests for cost analytics API routes.

Part of NEM-5024 Phase 2: Cost Analytics Dashboard.
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.api.routes.cost_analytics import (
    _build_cost_history,
    _build_model_cost_breakdown,
    _calculate_gpu_cost,
    _calculate_token_cost,
    _validate_date_range,
    get_cost_analytics,
    get_cost_trends,
)
from backend.api.schemas.cost_analytics import (
    CostAnalyticsResponse,
    CostTrendResponse,
)
from backend.services.cost_tracker import BudgetStatus, DailyUsage


@pytest.fixture
def mock_daily_usage():
    """Create mock daily usage data."""
    return DailyUsage(
        date=date.today(),
        total_input_tokens=15000,
        total_output_tokens=5000,
        total_gpu_seconds=125.5,
        total_images_processed=150,
        total_enrichment_operations=42,
        total_estimated_cost_usd=0.0523,
        event_count=25,
        usage_by_model={"nemotron": 0.0234, "yolo26": 0.0189},
    )


@pytest.fixture
def mock_budget_status():
    """Create mock budget status."""
    return BudgetStatus(
        daily_limit_usd=1.0,
        monthly_limit_usd=25.0,
        daily_used_usd=0.0523,
        monthly_used_usd=1.569,
        daily_remaining_usd=0.9477,
        monthly_remaining_usd=23.431,
        daily_utilization_ratio=0.0523,
        monthly_utilization_ratio=0.06276,
        daily_exceeded=False,
        monthly_exceeded=False,
        warning_threshold_reached=False,
    )


@pytest.fixture
def mock_pricing():
    """Create mock pricing config."""
    pricing = MagicMock()
    pricing.input_cost_per_1k_tokens = 0.003
    pricing.output_cost_per_1k_tokens = 0.006
    pricing.gpu_cost_per_second = 0.000139
    return pricing


@pytest.fixture
def mock_cost_tracker(mock_daily_usage, mock_budget_status, mock_pricing):
    """Create a mock cost tracker."""
    tracker = MagicMock()
    tracker._pricing = mock_pricing
    tracker.get_daily_usage.return_value = mock_daily_usage
    tracker.get_budget_status = AsyncMock(return_value=mock_budget_status)
    tracker.get_usage_summary.return_value = {
        "today": {
            "cost_usd": 0.0523,
            "input_tokens": 15000,
            "output_tokens": 5000,
            "gpu_seconds": 125.5,
            "events": 25,
        },
        "this_month": {"cost_usd": 1.569, "total_tokens": 200000, "gpu_seconds": 1255.0},
        "all_time": {
            "total_cost_usd": 5.234,
            "total_events": 250,
            "avg_cost_per_event_usd": 0.0021,
            "days_tracked": 30,
        },
        "budgets": {
            "daily_limit_usd": 1.0,
            "monthly_limit_usd": 25.0,
            "warning_threshold": 0.8,
        },
        "pricing": {
            "input_cost_per_1k_tokens": 0.003,
            "output_cost_per_1k_tokens": 0.006,
            "gpu_cost_per_second": 0.000139,
        },
    }
    return tracker


class TestValidateDateRange:
    """Tests for _validate_date_range helper function."""

    @pytest.mark.unit
    def test_valid_date_range(self):
        """Test valid date range passes validation."""
        start = date(2026, 1, 1)
        end = date(2026, 1, 31)
        # Should not raise
        _validate_date_range(start, end)

    @pytest.mark.unit
    def test_same_date_valid(self):
        """Test same start and end date is valid."""
        today = date.today()
        # Should not raise
        _validate_date_range(today, today)

    @pytest.mark.unit
    def test_start_after_end_raises(self):
        """Test start date after end date raises HTTPException."""
        start = date(2026, 1, 31)
        end = date(2026, 1, 1)
        with pytest.raises(HTTPException) as exc_info:
            _validate_date_range(start, end)
        assert exc_info.value.status_code == 400
        assert "start_date must be before or equal to end_date" in str(exc_info.value.detail)

    @pytest.mark.unit
    def test_date_range_exceeds_maximum(self):
        """Test date range exceeding maximum raises HTTPException."""
        start = date(2025, 1, 1)
        end = date(2025, 12, 31)  # 365 days
        with pytest.raises(HTTPException) as exc_info:
            _validate_date_range(start, end)
        assert exc_info.value.status_code == 400
        assert "Date range exceeds maximum allowed" in str(exc_info.value.detail)

    @pytest.mark.unit
    def test_max_allowed_range(self):
        """Test maximum allowed range (90 days) is valid."""
        start = date(2026, 1, 1)
        end = date(2026, 3, 31)  # 90 days
        # Should not raise
        _validate_date_range(start, end)


class TestCalculateTokenCost:
    """Tests for _calculate_token_cost helper function."""

    @pytest.mark.unit
    def test_token_cost_calculation(self, mock_daily_usage, mock_pricing):
        """Test token cost calculation."""
        with patch("backend.api.routes.cost_analytics.get_cost_tracker") as mock_get:
            mock_tracker = MagicMock()
            mock_tracker._pricing = mock_pricing
            mock_get.return_value = mock_tracker

            cost = _calculate_token_cost(mock_daily_usage)

            # 15000 input tokens * 0.003 / 1000 = 0.045
            # 5000 output tokens * 0.006 / 1000 = 0.03
            # Total = 0.075
            assert cost == pytest.approx(0.075, rel=0.001)

    @pytest.mark.unit
    def test_token_cost_with_no_usage(self):
        """Test token cost returns 0 with no usage data."""
        cost = _calculate_token_cost(None)
        assert cost == 0.0


class TestCalculateGpuCost:
    """Tests for _calculate_gpu_cost helper function."""

    @pytest.mark.unit
    def test_gpu_cost_calculation(self, mock_daily_usage, mock_pricing):
        """Test GPU cost calculation."""
        with patch("backend.api.routes.cost_analytics.get_cost_tracker") as mock_get:
            mock_tracker = MagicMock()
            mock_tracker._pricing = mock_pricing
            mock_get.return_value = mock_tracker

            cost = _calculate_gpu_cost(mock_daily_usage)

            # 125.5 seconds * 0.000139 = 0.01744
            assert cost == pytest.approx(0.01744, rel=0.01)

    @pytest.mark.unit
    def test_gpu_cost_with_no_usage(self):
        """Test GPU cost returns 0 with no usage data."""
        cost = _calculate_gpu_cost(None)
        assert cost == 0.0


class TestBuildModelCostBreakdown:
    """Tests for _build_model_cost_breakdown helper function."""

    @pytest.mark.unit
    def test_model_breakdown_from_usage(self, mock_daily_usage):
        """Test model cost breakdown is built correctly."""
        breakdown = _build_model_cost_breakdown(mock_daily_usage)

        assert len(breakdown) == 2
        model_names = {m.model for m in breakdown}
        assert model_names == {"nemotron", "yolo26"}

    @pytest.mark.unit
    def test_model_breakdown_no_usage(self):
        """Test model breakdown with no usage data."""
        breakdown = _build_model_cost_breakdown(None)
        assert breakdown == []

    @pytest.mark.unit
    def test_model_breakdown_empty_models(self):
        """Test model breakdown with empty usage_by_model."""
        usage = MagicMock()
        usage.usage_by_model = {}
        breakdown = _build_model_cost_breakdown(usage)
        assert breakdown == []


class TestBuildCostHistory:
    """Tests for _build_cost_history helper function."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cost_history_builds_correctly(
        self, mock_cost_tracker, mock_daily_usage, mock_pricing, mock_db_session
    ):
        """Test cost history is built for the correct number of days."""
        with patch("backend.api.routes.cost_analytics.get_cost_tracker") as mock_get:
            mock_tracker = MagicMock()
            mock_tracker._pricing = mock_pricing
            mock_tracker.get_daily_usage.return_value = mock_daily_usage
            mock_get.return_value = mock_tracker

            today = date.today()
            history = await _build_cost_history(mock_tracker, mock_db_session, today, 7)

            assert len(history) == 7
            # Verify dates are in chronological order
            dates = [h.date for h in history]
            assert dates == sorted(dates)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cost_history_handles_no_data(self, mock_pricing, mock_db_session):
        """Test cost history handles days with no data."""
        with patch("backend.api.routes.cost_analytics.get_cost_tracker") as mock_get:
            mock_tracker = MagicMock()
            mock_tracker._pricing = mock_pricing
            mock_tracker.get_daily_usage.return_value = None
            mock_get.return_value = mock_tracker

            today = date.today()
            history = await _build_cost_history(mock_tracker, mock_db_session, today, 3)

            assert len(history) == 3
            for entry in history:
                assert entry.total_cost_usd == 0.0
                assert entry.event_count == 0


class TestGetCostAnalytics:
    """Tests for GET /api/analytics/costs endpoint."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_cost_analytics_success(self, mock_cost_tracker, mock_db_session):
        """Test successful retrieval of cost analytics."""
        # Configure db.execute to return a proper result with scalar() = 100
        mock_result = MagicMock()
        mock_result.scalar.return_value = 100
        mock_db_session.execute.return_value = mock_result

        with patch(
            "backend.api.routes.cost_analytics.get_cost_tracker", return_value=mock_cost_tracker
        ):
            response = await get_cost_analytics(mock_db_session)

        assert isinstance(response, CostAnalyticsResponse)

        # Verify response structure
        assert response.today is not None
        assert response.daily_budget is not None
        assert response.monthly_budget is not None
        assert response.token_usage is not None
        assert response.cost_by_model is not None
        assert response.efficiency is not None
        assert response.cost_history is not None
        assert response.pricing is not None
        assert response.last_updated is not None

        # Verify today's data
        assert response.today.total_cost_usd == 0.0523
        assert response.today.event_count == 25

        # Verify budget data
        assert response.daily_budget.period == "daily"
        assert response.daily_budget.limit_usd == 1.0
        assert response.daily_budget.exceeded is False

        assert response.monthly_budget.period == "monthly"
        assert response.monthly_budget.limit_usd == 25.0

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_cost_analytics_no_usage_data(self, mock_cost_tracker, mock_db_session):
        """Test cost analytics when no usage data exists."""
        mock_cost_tracker.get_daily_usage.return_value = None
        mock_cost_tracker.get_usage_summary.return_value = {
            "today": {
                "cost_usd": 0.0,
                "input_tokens": 0,
                "output_tokens": 0,
                "gpu_seconds": 0.0,
                "events": 0,
            },
            "this_month": {"cost_usd": 0.0, "total_tokens": 0, "gpu_seconds": 0.0},
            "all_time": {
                "total_cost_usd": 0.0,
                "total_events": 0,
                "avg_cost_per_event_usd": 0.0,
                "days_tracked": 0,
            },
            "budgets": {
                "daily_limit_usd": 1.0,
                "monthly_limit_usd": 25.0,
                "warning_threshold": 0.8,
            },
            "pricing": {
                "input_cost_per_1k_tokens": 0.003,
                "output_cost_per_1k_tokens": 0.006,
                "gpu_cost_per_second": 0.000139,
            },
        }

        # Configure db.execute to return 0 detections
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_db_session.execute.return_value = mock_result

        with patch(
            "backend.api.routes.cost_analytics.get_cost_tracker", return_value=mock_cost_tracker
        ):
            response = await get_cost_analytics(mock_db_session)

        # Verify defaults when no data
        assert response.today.total_cost_usd == 0.0
        assert response.today.event_count == 0
        assert response.cost_by_model == []


class TestGetCostTrends:
    """Tests for GET /api/analytics/costs/trends endpoint."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_cost_trends_success(self, mock_cost_tracker):
        """Test successful retrieval of cost trends."""
        with patch(
            "backend.api.routes.cost_analytics.get_cost_tracker", return_value=mock_cost_tracker
        ):
            start = date(2026, 1, 25)
            end = date(2026, 1, 31)
            response = await get_cost_trends(start_date=start, end_date=end)

        assert isinstance(response, CostTrendResponse)
        assert len(response.data_points) == 7
        assert response.start_date == "2026-01-25"
        assert response.end_date == "2026-01-31"
        assert response.total_cost_usd > 0

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_cost_trends_single_day(self, mock_cost_tracker):
        """Test cost trends for a single day."""
        with patch(
            "backend.api.routes.cost_analytics.get_cost_tracker", return_value=mock_cost_tracker
        ):
            day = date(2026, 1, 31)
            response = await get_cost_trends(start_date=day, end_date=day)

        assert len(response.data_points) == 1
        assert response.data_points[0].date == "2026-01-31"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_cost_trends_no_data(self, mock_cost_tracker):
        """Test cost trends when no usage data exists."""
        mock_cost_tracker.get_daily_usage.return_value = None

        with patch(
            "backend.api.routes.cost_analytics.get_cost_tracker", return_value=mock_cost_tracker
        ):
            start = date(2026, 1, 25)
            end = date(2026, 1, 31)
            response = await get_cost_trends(start_date=start, end_date=end)

        # All data points should have zero cost
        for point in response.data_points:
            assert point.cost_usd == 0.0
        assert response.total_cost_usd == 0.0

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_cost_trends_invalid_date_range(self):
        """Test cost trends with invalid date range (start after end)."""
        with pytest.raises(HTTPException) as exc_info:
            await get_cost_trends(start_date=date(2026, 1, 31), end_date=date(2026, 1, 25))
        assert exc_info.value.status_code == 400
        assert "start_date must be before or equal to end_date" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_cost_trends_date_range_exceeded(self):
        """Test cost trends with date range exceeding maximum."""
        with pytest.raises(HTTPException) as exc_info:
            await get_cost_trends(start_date=date(2025, 1, 1), end_date=date(2026, 1, 31))
        assert exc_info.value.status_code == 400
        assert "Date range exceeds maximum allowed" in str(exc_info.value.detail)


class TestCostAnalyticsSchemas:
    """Tests for cost analytics response schema validation."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_daily_cost_entry_schema(self, mock_cost_tracker, mock_db_session):
        """Test DailyCostEntry schema validation."""
        # Configure db.execute to return a proper result with scalar() = 150
        mock_result = MagicMock()
        mock_result.scalar.return_value = 150
        mock_db_session.execute.return_value = mock_result

        with patch(
            "backend.api.routes.cost_analytics.get_cost_tracker", return_value=mock_cost_tracker
        ):
            response = await get_cost_analytics(mock_db_session)

        # Verify today entry has all required fields
        today = response.today
        assert hasattr(today, "date")
        assert hasattr(today, "total_cost_usd")
        assert hasattr(today, "token_cost_usd")
        assert hasattr(today, "gpu_cost_usd")
        assert hasattr(today, "event_count")
        assert hasattr(today, "detection_count")

        # Verify types
        assert isinstance(today.total_cost_usd, int | float)
        assert isinstance(today.event_count, int)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_budget_utilization_schema(self, mock_cost_tracker, mock_db_session):
        """Test BudgetUtilization schema validation."""
        # Configure db.execute to return a proper result with scalar() = 150
        mock_result = MagicMock()
        mock_result.scalar.return_value = 150
        mock_db_session.execute.return_value = mock_result

        with patch(
            "backend.api.routes.cost_analytics.get_cost_tracker", return_value=mock_cost_tracker
        ):
            response = await get_cost_analytics(mock_db_session)

        # Verify daily budget has all required fields
        daily_budget = response.daily_budget
        assert daily_budget.period == "daily"
        assert hasattr(daily_budget, "limit_usd")
        assert hasattr(daily_budget, "used_usd")
        assert hasattr(daily_budget, "remaining_usd")
        assert hasattr(daily_budget, "utilization_ratio")
        assert hasattr(daily_budget, "exceeded")
        assert hasattr(daily_budget, "warning_reached")

        # Verify monthly budget
        monthly_budget = response.monthly_budget
        assert monthly_budget.period == "monthly"
