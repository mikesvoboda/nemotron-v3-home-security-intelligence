"""Pydantic schemas for cost analytics API.

This module defines schemas for the Cost Analytics Dashboard endpoints,
exposing token costs, GPU costs, budget utilization, and cost trends.

Part of NEM-5024 Phase 2: Cost Analytics Dashboard.
"""

from pydantic import BaseModel, ConfigDict, Field


class ModelCostBreakdown(BaseModel):
    """Cost breakdown by model."""

    model: str = Field(..., description="Model identifier (e.g., 'nemotron', 'yolo26')")
    cost_usd: float = Field(..., ge=0, description="Total cost in USD for this model")
    gpu_seconds: float = Field(..., ge=0, description="Total GPU time consumed in seconds")
    request_count: int = Field(..., ge=0, description="Number of inference requests")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "model": "nemotron",
                "cost_usd": 0.0234,
                "gpu_seconds": 125.5,
                "request_count": 42,
            }
        }
    )


class TokenUsageMetrics(BaseModel):
    """Token usage metrics for LLM models."""

    input_tokens: int = Field(..., ge=0, description="Total input/prompt tokens")
    output_tokens: int = Field(..., ge=0, description="Total output/completion tokens")
    total_tokens: int = Field(..., ge=0, description="Total tokens (input + output)")
    token_cost_usd: float = Field(..., ge=0, description="Estimated cost for tokens in USD")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "input_tokens": 15000,
                "output_tokens": 5000,
                "total_tokens": 20000,
                "token_cost_usd": 0.075,
            }
        }
    )


class DailyCostEntry(BaseModel):
    """Cost data for a single day."""

    date: str = Field(..., description="Date in YYYY-MM-DD format")
    total_cost_usd: float = Field(..., ge=0, description="Total estimated cost for the day")
    token_cost_usd: float = Field(..., ge=0, description="Token-related cost")
    gpu_cost_usd: float = Field(..., ge=0, description="GPU time cost")
    event_count: int = Field(..., ge=0, description="Number of security events analyzed")
    detection_count: int = Field(..., ge=0, description="Number of detections processed")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date": "2026-01-31",
                "total_cost_usd": 0.0523,
                "token_cost_usd": 0.0315,
                "gpu_cost_usd": 0.0208,
                "event_count": 25,
                "detection_count": 150,
            }
        }
    )


class BudgetUtilization(BaseModel):
    """Budget utilization metrics."""

    period: str = Field(..., description="Budget period: 'daily' or 'monthly'")
    limit_usd: float = Field(..., ge=0, description="Budget limit in USD")
    used_usd: float = Field(..., ge=0, description="Amount used in USD")
    remaining_usd: float = Field(..., ge=0, description="Amount remaining in USD")
    utilization_ratio: float = Field(..., ge=0, description="Utilization ratio (0.0 to 1.0+)")
    exceeded: bool = Field(..., description="Whether budget has been exceeded")
    warning_reached: bool = Field(..., description="Whether warning threshold reached")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "period": "daily",
                "limit_usd": 1.0,
                "used_usd": 0.75,
                "remaining_usd": 0.25,
                "utilization_ratio": 0.75,
                "exceeded": False,
                "warning_reached": False,
            }
        }
    )


class CostEfficiencyMetrics(BaseModel):
    """Cost efficiency metrics."""

    cost_per_detection_usd: float = Field(
        ..., ge=0, description="Average cost per detection in USD"
    )
    cost_per_event_usd: float = Field(..., ge=0, description="Average cost per event in USD")
    total_detections: int = Field(..., ge=0, description="Total detections processed")
    total_events: int = Field(..., ge=0, description="Total security events analyzed")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cost_per_detection_usd": 0.00002,
                "cost_per_event_usd": 0.0021,
                "total_detections": 15000,
                "total_events": 250,
            }
        }
    )


class PricingConfig(BaseModel):
    """Cloud equivalent pricing configuration."""

    input_cost_per_1k_tokens: float = Field(
        ..., ge=0, description="Cost per 1000 input tokens in USD"
    )
    output_cost_per_1k_tokens: float = Field(
        ..., ge=0, description="Cost per 1000 output tokens in USD"
    )
    gpu_cost_per_second: float = Field(..., ge=0, description="GPU cost per second in USD")
    detection_cost_per_image: float = Field(
        ..., ge=0, description="Detection cost per image in USD"
    )
    enrichment_cost_per_operation: float = Field(
        ..., ge=0, description="Enrichment cost per operation in USD"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "input_cost_per_1k_tokens": 0.003,
                "output_cost_per_1k_tokens": 0.006,
                "gpu_cost_per_second": 0.000139,
                "detection_cost_per_image": 0.00002,
                "enrichment_cost_per_operation": 0.00001,
            }
        }
    )


class CostAnalyticsResponse(BaseModel):
    """Full cost analytics response."""

    # Current period summaries
    today: DailyCostEntry = Field(..., description="Today's cost summary")
    daily_budget: BudgetUtilization = Field(..., description="Daily budget utilization")
    monthly_budget: BudgetUtilization = Field(..., description="Monthly budget utilization")

    # Token metrics
    token_usage: TokenUsageMetrics = Field(..., description="Token usage metrics")

    # Cost breakdowns
    cost_by_model: list[ModelCostBreakdown] = Field(..., description="Cost breakdown by model")

    # Efficiency metrics
    efficiency: CostEfficiencyMetrics = Field(..., description="Cost efficiency metrics")

    # Historical data
    cost_history: list[DailyCostEntry] = Field(..., description="Daily cost history (last 30 days)")

    # Configuration
    pricing: PricingConfig = Field(..., description="Current pricing configuration")

    # Metadata
    last_updated: str = Field(..., description="ISO timestamp of last update")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "today": {
                    "date": "2026-01-31",
                    "total_cost_usd": 0.0523,
                    "token_cost_usd": 0.0315,
                    "gpu_cost_usd": 0.0208,
                    "event_count": 25,
                    "detection_count": 150,
                },
                "daily_budget": {
                    "period": "daily",
                    "limit_usd": 1.0,
                    "used_usd": 0.0523,
                    "remaining_usd": 0.9477,
                    "utilization_ratio": 0.0523,
                    "exceeded": False,
                    "warning_reached": False,
                },
                "monthly_budget": {
                    "period": "monthly",
                    "limit_usd": 25.0,
                    "used_usd": 1.569,
                    "remaining_usd": 23.431,
                    "utilization_ratio": 0.06276,
                    "exceeded": False,
                    "warning_reached": False,
                },
                "token_usage": {
                    "input_tokens": 15000,
                    "output_tokens": 5000,
                    "total_tokens": 20000,
                    "token_cost_usd": 0.075,
                },
                "cost_by_model": [
                    {
                        "model": "nemotron",
                        "cost_usd": 0.0234,
                        "gpu_seconds": 125.5,
                        "request_count": 42,
                    }
                ],
                "efficiency": {
                    "cost_per_detection_usd": 0.00002,
                    "cost_per_event_usd": 0.0021,
                    "total_detections": 15000,
                    "total_events": 250,
                },
                "cost_history": [],
                "pricing": {
                    "input_cost_per_1k_tokens": 0.003,
                    "output_cost_per_1k_tokens": 0.006,
                    "gpu_cost_per_second": 0.000139,
                    "detection_cost_per_image": 0.00002,
                    "enrichment_cost_per_operation": 0.00001,
                },
                "last_updated": "2026-01-31T12:00:00Z",
            }
        }
    )


class CostTrendDataPoint(BaseModel):
    """Data point for cost trend charts."""

    date: str = Field(..., description="Date in YYYY-MM-DD format")
    cost_usd: float = Field(..., ge=0, description="Total cost for the period")

    model_config = ConfigDict(
        json_schema_extra={"example": {"date": "2026-01-31", "cost_usd": 0.0523}}
    )


class CostTrendResponse(BaseModel):
    """Response for cost trend endpoint."""

    data_points: list[CostTrendDataPoint] = Field(..., description="Cost trend data points")
    total_cost_usd: float = Field(..., ge=0, description="Total cost over the period")
    start_date: str = Field(..., description="Start date of the trend")
    end_date: str = Field(..., description="End date of the trend")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data_points": [
                    {"date": "2026-01-25", "cost_usd": 0.045},
                    {"date": "2026-01-26", "cost_usd": 0.052},
                ],
                "total_cost_usd": 0.097,
                "start_date": "2026-01-25",
                "end_date": "2026-01-26",
            }
        }
    )
