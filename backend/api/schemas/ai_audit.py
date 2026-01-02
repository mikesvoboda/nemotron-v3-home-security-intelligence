"""Pydantic schemas for AI audit API endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ModelContributions(BaseModel):
    """Model contribution flags."""

    rtdetr: bool = Field(False, description="RT-DETR object detection")
    florence: bool = Field(False, description="Florence-2 vision attributes")
    clip: bool = Field(False, description="CLIP embeddings")
    violence: bool = Field(False, description="Violence detection")
    clothing: bool = Field(False, description="Clothing analysis")
    vehicle: bool = Field(False, description="Vehicle classification")
    pet: bool = Field(False, description="Pet classification")
    weather: bool = Field(False, description="Weather classification")
    image_quality: bool = Field(False, description="Image quality assessment")
    zones: bool = Field(False, description="Zone analysis")
    baseline: bool = Field(False, description="Baseline comparison")
    cross_camera: bool = Field(False, description="Cross-camera correlation")


class QualityScores(BaseModel):
    """Self-evaluation quality scores (1-5 scale)."""

    context_usage: float | None = Field(None, ge=1, le=5)
    reasoning_coherence: float | None = Field(None, ge=1, le=5)
    risk_justification: float | None = Field(None, ge=1, le=5)
    consistency: float | None = Field(None, ge=1, le=5)
    overall: float | None = Field(None, ge=1, le=5)


class PromptImprovements(BaseModel):
    """Prompt improvement suggestions from self-evaluation."""

    missing_context: list[str] = Field(default_factory=list)
    confusing_sections: list[str] = Field(default_factory=list)
    unused_data: list[str] = Field(default_factory=list)
    format_suggestions: list[str] = Field(default_factory=list)
    model_gaps: list[str] = Field(default_factory=list)


class EventAuditResponse(BaseModel):
    """Full audit response for a single event."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    audited_at: datetime
    is_fully_evaluated: bool

    # Model contributions
    contributions: ModelContributions

    # Prompt metrics
    prompt_length: int
    prompt_token_estimate: int
    enrichment_utilization: float

    # Quality scores (None if not evaluated)
    scores: QualityScores

    # Consistency check
    consistency_risk_score: int | None = None
    consistency_diff: int | None = None

    # Self-evaluation text
    self_eval_critique: str | None = None

    # Prompt improvements
    improvements: PromptImprovements


class AuditStatsResponse(BaseModel):
    """Aggregate audit statistics."""

    total_events: int
    audited_events: int
    fully_evaluated_events: int

    avg_quality_score: float | None
    avg_consistency_rate: float | None
    avg_enrichment_utilization: float | None

    # Model contribution rates (0-1)
    model_contribution_rates: dict[str, float]

    # Audits by day for trending
    audits_by_day: list[dict]


class ModelLeaderboardEntry(BaseModel):
    """Single entry in model leaderboard."""

    model_name: str
    contribution_rate: float
    quality_correlation: float | None
    event_count: int


class LeaderboardResponse(BaseModel):
    """Model leaderboard response."""

    entries: list[ModelLeaderboardEntry]
    period_days: int


class RecommendationItem(BaseModel):
    """Single recommendation item."""

    category: str  # missing_context, unused_data, model_gaps, etc.
    suggestion: str
    frequency: int  # How many events mentioned this
    priority: str  # high, medium, low


class RecommendationsResponse(BaseModel):
    """Aggregated recommendations response."""

    recommendations: list[RecommendationItem]
    total_events_analyzed: int


class BatchAuditRequest(BaseModel):
    """Request for batch audit processing."""

    limit: int = Field(100, ge=1, le=1000)
    min_risk_score: int | None = Field(None, ge=0, le=100)
    force_reevaluate: bool = False


class BatchAuditResponse(BaseModel):
    """Response for batch audit request."""

    queued_count: int
    message: str
