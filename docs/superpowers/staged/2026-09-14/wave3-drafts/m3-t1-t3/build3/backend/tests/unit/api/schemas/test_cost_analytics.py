"""Unit tests for cost analytics schemas.

Part of NEM-5024 Phase 2: Cost Analytics Dashboard.
"""

import pytest
from pydantic import ValidationError

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


class TestDailyCostEntry:
    """Tests for DailyCostEntry schema."""

    @pytest.mark.unit
    def test_valid_daily_cost_entry(self):
        """Test creating a valid DailyCostEntry."""
        entry = DailyCostEntry(
            date="2026-01-31",
            total_cost_usd=0.0523,
            token_cost_usd=0.0315,
            gpu_cost_usd=0.0208,
            event_count=25,
            detection_count=150,
        )

        assert entry.date == "2026-01-31"
        assert entry.total_cost_usd == 0.0523
        assert entry.event_count == 25

    @pytest.mark.unit
    def test_zero_values_allowed(self):
        """Test that zero values are allowed."""
        entry = DailyCostEntry(
            date="2026-01-31",
            total_cost_usd=0.0,
            token_cost_usd=0.0,
            gpu_cost_usd=0.0,
            event_count=0,
            detection_count=0,
        )

        assert entry.total_cost_usd == 0.0
        assert entry.event_count == 0

    @pytest.mark.unit
    def test_negative_cost_rejected(self):
        """Test that negative costs are rejected."""
        with pytest.raises(ValidationError):
            DailyCostEntry(
                date="2026-01-31",
                total_cost_usd=-0.01,
                token_cost_usd=0.0,
                gpu_cost_usd=0.0,
                event_count=0,
                detection_count=0,
            )

    @pytest.mark.unit
    def test_negative_count_rejected(self):
        """Test that negative counts are rejected."""
        with pytest.raises(ValidationError):
            DailyCostEntry(
                date="2026-01-31",
                total_cost_usd=0.0,
                token_cost_usd=0.0,
                gpu_cost_usd=0.0,
                event_count=-1,
                detection_count=0,
            )


class TestBudgetUtilization:
    """Tests for BudgetUtilization schema."""

    @pytest.mark.unit
    def test_valid_budget_utilization(self):
        """Test creating a valid BudgetUtilization."""
        budget = BudgetUtilization(
            period="daily",
            limit_usd=1.0,
            used_usd=0.5,
            remaining_usd=0.5,
            utilization_ratio=0.5,
            exceeded=False,
            warning_reached=False,
        )

        assert budget.period == "daily"
        assert budget.utilization_ratio == 0.5
        assert budget.exceeded is False

    @pytest.mark.unit
    def test_exceeded_budget(self):
        """Test budget with exceeded flag."""
        budget = BudgetUtilization(
            period="monthly",
            limit_usd=25.0,
            used_usd=30.0,
            remaining_usd=0.0,
            utilization_ratio=1.2,
            exceeded=True,
            warning_reached=True,
        )

        assert budget.exceeded is True
        assert budget.utilization_ratio == 1.2

    @pytest.mark.unit
    def test_unlimited_budget(self):
        """Test unlimited budget (limit = 0)."""
        budget = BudgetUtilization(
            period="daily",
            limit_usd=0.0,
            used_usd=5.0,
            remaining_usd=0.0,
            utilization_ratio=0.0,
            exceeded=False,
            warning_reached=False,
        )

        assert budget.limit_usd == 0.0
        assert budget.exceeded is False


class TestTokenUsageMetrics:
    """Tests for TokenUsageMetrics schema."""

    @pytest.mark.unit
    def test_valid_token_usage(self):
        """Test creating valid token usage metrics."""
        usage = TokenUsageMetrics(
            input_tokens=15000,
            output_tokens=5000,
            total_tokens=20000,
            token_cost_usd=0.075,
        )

        assert usage.total_tokens == 20000
        assert usage.token_cost_usd == 0.075

    @pytest.mark.unit
    def test_zero_tokens(self):
        """Test zero token counts."""
        usage = TokenUsageMetrics(
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            token_cost_usd=0.0,
        )

        assert usage.total_tokens == 0


class TestModelCostBreakdown:
    """Tests for ModelCostBreakdown schema."""

    @pytest.mark.unit
    def test_valid_model_breakdown(self):
        """Test creating valid model cost breakdown."""
        breakdown = ModelCostBreakdown(
            model="nemotron",
            cost_usd=0.0234,
            gpu_seconds=125.5,
            request_count=42,
        )

        assert breakdown.model == "nemotron"
        assert breakdown.cost_usd == 0.0234

    @pytest.mark.unit
    def test_negative_values_rejected(self):
        """Test that negative values are rejected."""
        with pytest.raises(ValidationError):
            ModelCostBreakdown(
                model="nemotron",
                cost_usd=-0.01,
                gpu_seconds=0.0,
                request_count=0,
            )


class TestCostEfficiencyMetrics:
    """Tests for CostEfficiencyMetrics schema."""

    @pytest.mark.unit
    def test_valid_efficiency_metrics(self):
        """Test creating valid efficiency metrics."""
        metrics = CostEfficiencyMetrics(
            cost_per_detection_usd=0.00002,
            cost_per_event_usd=0.0021,
            total_detections=15000,
            total_events=250,
        )

        assert metrics.cost_per_event_usd == 0.0021
        assert metrics.total_events == 250


class TestPricingConfig:
    """Tests for PricingConfig schema."""

    @pytest.mark.unit
    def test_valid_pricing_config(self):
        """Test creating valid pricing config."""
        config = PricingConfig(
            input_cost_per_1k_tokens=0.003,
            output_cost_per_1k_tokens=0.006,
            gpu_cost_per_second=0.000139,
            detection_cost_per_image=0.00002,
            enrichment_cost_per_operation=0.00001,
        )

        assert config.input_cost_per_1k_tokens == 0.003
        assert config.gpu_cost_per_second == 0.000139


class TestCostTrendDataPoint:
    """Tests for CostTrendDataPoint schema."""

    @pytest.mark.unit
    def test_valid_trend_data_point(self):
        """Test creating valid trend data point."""
        point = CostTrendDataPoint(
            date="2026-01-31",
            cost_usd=0.0523,
        )

        assert point.date == "2026-01-31"
        assert point.cost_usd == 0.0523


class TestCostTrendResponse:
    """Tests for CostTrendResponse schema."""

    @pytest.mark.unit
    def test_valid_trend_response(self):
        """Test creating valid trend response."""
        response = CostTrendResponse(
            data_points=[
                CostTrendDataPoint(date="2026-01-30", cost_usd=0.045),
                CostTrendDataPoint(date="2026-01-31", cost_usd=0.052),
            ],
            total_cost_usd=0.097,
            start_date="2026-01-30",
            end_date="2026-01-31",
        )

        assert len(response.data_points) == 2
        assert response.total_cost_usd == 0.097

    @pytest.mark.unit
    def test_empty_data_points(self):
        """Test with empty data points."""
        response = CostTrendResponse(
            data_points=[],
            total_cost_usd=0.0,
            start_date="2026-01-30",
            end_date="2026-01-31",
        )

        assert len(response.data_points) == 0


class TestCostAnalyticsResponse:
    """Tests for CostAnalyticsResponse schema."""

    @pytest.mark.unit
    def test_valid_full_response(self):
        """Test creating valid full analytics response."""
        response = CostAnalyticsResponse(
            today=DailyCostEntry(
                date="2026-01-31",
                total_cost_usd=0.0523,
                token_cost_usd=0.0315,
                gpu_cost_usd=0.0208,
                event_count=25,
                detection_count=150,
            ),
            daily_budget=BudgetUtilization(
                period="daily",
                limit_usd=1.0,
                used_usd=0.0523,
                remaining_usd=0.9477,
                utilization_ratio=0.0523,
                exceeded=False,
                warning_reached=False,
            ),
            monthly_budget=BudgetUtilization(
                period="monthly",
                limit_usd=25.0,
                used_usd=1.569,
                remaining_usd=23.431,
                utilization_ratio=0.06276,
                exceeded=False,
                warning_reached=False,
            ),
            token_usage=TokenUsageMetrics(
                input_tokens=15000,
                output_tokens=5000,
                total_tokens=20000,
                token_cost_usd=0.075,
            ),
            cost_by_model=[
                ModelCostBreakdown(
                    model="nemotron",
                    cost_usd=0.0234,
                    gpu_seconds=125.5,
                    request_count=42,
                )
            ],
            efficiency=CostEfficiencyMetrics(
                cost_per_detection_usd=0.00002,
                cost_per_event_usd=0.0021,
                total_detections=15000,
                total_events=250,
            ),
            cost_history=[],
            pricing=PricingConfig(
                input_cost_per_1k_tokens=0.003,
                output_cost_per_1k_tokens=0.006,
                gpu_cost_per_second=0.000139,
                detection_cost_per_image=0.00002,
                enrichment_cost_per_operation=0.00001,
            ),
            last_updated="2026-01-31T12:00:00Z",
        )

        assert response.today.total_cost_usd == 0.0523
        assert response.daily_budget.period == "daily"
        assert len(response.cost_by_model) == 1

    @pytest.mark.unit
    def test_response_serialization(self):
        """Test response JSON serialization."""
        response = CostAnalyticsResponse(
            today=DailyCostEntry(
                date="2026-01-31",
                total_cost_usd=0.0523,
                token_cost_usd=0.0315,
                gpu_cost_usd=0.0208,
                event_count=25,
                detection_count=150,
            ),
            daily_budget=BudgetUtilization(
                period="daily",
                limit_usd=1.0,
                used_usd=0.0523,
                remaining_usd=0.9477,
                utilization_ratio=0.0523,
                exceeded=False,
                warning_reached=False,
            ),
            monthly_budget=BudgetUtilization(
                period="monthly",
                limit_usd=25.0,
                used_usd=1.569,
                remaining_usd=23.431,
                utilization_ratio=0.06276,
                exceeded=False,
                warning_reached=False,
            ),
            token_usage=TokenUsageMetrics(
                input_tokens=15000,
                output_tokens=5000,
                total_tokens=20000,
                token_cost_usd=0.075,
            ),
            cost_by_model=[],
            efficiency=CostEfficiencyMetrics(
                cost_per_detection_usd=0.00002,
                cost_per_event_usd=0.0021,
                total_detections=15000,
                total_events=250,
            ),
            cost_history=[],
            pricing=PricingConfig(
                input_cost_per_1k_tokens=0.003,
                output_cost_per_1k_tokens=0.006,
                gpu_cost_per_second=0.000139,
                detection_cost_per_image=0.00002,
                enrichment_cost_per_operation=0.00001,
            ),
            last_updated="2026-01-31T12:00:00Z",
        )

        json_data = response.model_dump()
        assert json_data["today"]["date"] == "2026-01-31"
        assert json_data["daily_budget"]["period"] == "daily"
