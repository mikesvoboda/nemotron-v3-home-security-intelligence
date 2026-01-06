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


class ExampleImprovement(BaseModel):
    """Example of how a suggestion could improve a specific event's analysis.

    Shows the potential impact of applying a suggestion by comparing
    before/after risk scores for a real event.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "eventId": 142,
                "beforeScore": 65,
                "estimatedAfterScore": 40,
            }
        },
    )

    event_id: int = Field(
        ...,
        alias="eventId",
        description="The event ID used as an example",
    )
    before_score: int = Field(
        ...,
        ge=0,
        le=100,
        alias="beforeScore",
        description="Risk score with original prompt",
    )
    estimated_after_score: int = Field(
        ...,
        ge=0,
        le=100,
        alias="estimatedAfterScore",
        description="Estimated risk score if suggestion is applied",
    )


class EnrichedSuggestion(BaseModel):
    """Enhanced suggestion schema for smart prompt modification.

    Extends the basic recommendation with fields for:
    - Smart application: Identifies where and how to insert the suggestion
    - Learning mode: Explains impact with evidence from actual events

    Used by the Prompt Playground to transform AI audit recommendations
    into actionable prompt improvements through a progressive disclosure UX.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "category": "missing_context",
                "suggestion": "Time since last detected motion or event",
                "priority": "high",
                "frequency": 3,
                "targetSection": "Camera & Time Context",
                "insertionPoint": "append",
                "proposedVariable": "{time_since_last_event}",
                "proposedLabel": "Time Since Last Event:",
                "impactExplanation": "Adding time-since-last-event helps the AI distinguish between routine activity and unusual timing patterns. Events occurring shortly after previous motion are often less suspicious than isolated incidents.",
                "sourceEventIds": [142, 156, 189],
                "exampleImprovement": {
                    "eventId": 142,
                    "beforeScore": 65,
                    "estimatedAfterScore": 40,
                },
            }
        },
    )

    # Existing fields from RecommendationItem (no alias needed - single-word or standard)
    category: str = Field(
        ...,
        description="Suggestion category: missing_context, unused_data, model_gaps, format_suggestions",
    )
    suggestion: str = Field(
        ...,
        description="The improvement suggestion text",
    )
    priority: str = Field(
        ...,
        description="Priority level: high, medium, low",
    )
    frequency: int = Field(
        ...,
        ge=0,
        description="How many events mentioned this suggestion",
    )

    # Smart application fields
    target_section: str = Field(
        ...,
        alias="targetSection",
        description="Target section header in the prompt (e.g., 'Camera & Time Context')",
    )
    insertion_point: str = Field(
        ...,
        alias="insertionPoint",
        description="Where to insert: append, prepend, or replace",
    )
    proposed_variable: str = Field(
        ...,
        alias="proposedVariable",
        description="The variable to add (e.g., '{time_since_last_event}')",
    )
    proposed_label: str = Field(
        ...,
        alias="proposedLabel",
        description="Human-readable label for the variable (e.g., 'Time Since Last Event:')",
    )

    # Learning mode fields
    impact_explanation: str = Field(
        ...,
        alias="impactExplanation",
        description="Explanation of why this suggestion matters and its expected impact",
    )
    source_event_ids: list[int] = Field(
        default_factory=list,
        alias="sourceEventIds",
        description="IDs of events that triggered this suggestion",
    )

    # Optional improvement estimate
    example_improvement: ExampleImprovement | None = Field(
        None,
        alias="exampleImprovement",
        description="Optional example showing before/after scores for a specific event",
    )


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


# =============================================================================
# Prompt Playground Schemas
# =============================================================================


class ModelName(str):
    """Supported AI model names for prompt management."""

    NEMOTRON = "nemotron"
    FLORENCE2 = "florence2"
    YOLO_WORLD = "yolo_world"
    XCLIP = "xclip"
    FASHION_CLIP = "fashion_clip"

    @classmethod
    def all_models(cls) -> list[str]:
        """Return all supported model names."""
        return [cls.NEMOTRON, cls.FLORENCE2, cls.YOLO_WORLD, cls.XCLIP, cls.FASHION_CLIP]


class NemotronConfig(BaseModel):
    """Configuration for Nemotron LLM risk analyzer."""

    system_prompt: str = Field(..., description="Full system prompt text for risk analysis")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="LLM temperature setting")
    max_tokens: int = Field(2048, ge=100, le=8192, description="Maximum tokens in response")


class Florence2Config(BaseModel):
    """Configuration for Florence-2 VQA model."""

    vqa_queries: list[str] = Field(
        ...,
        description="List of visual question-answering queries",
        min_length=1,
    )


class YoloWorldConfig(BaseModel):
    """Configuration for YOLO-World object detection."""

    object_classes: list[str] = Field(
        ...,
        description="List of object classes to detect",
        min_length=1,
    )
    confidence_threshold: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="Minimum confidence for detections",
    )


class XClipConfig(BaseModel):
    """Configuration for X-CLIP action recognition."""

    action_classes: list[str] = Field(
        ...,
        description="List of action classes to recognize",
        min_length=1,
    )


class FashionClipConfig(BaseModel):
    """Configuration for FashionCLIP clothing analysis."""

    clothing_categories: list[str] = Field(
        ...,
        description="List of clothing categories to classify",
        min_length=1,
    )
    suspicious_indicators: list[str] = Field(
        default_factory=lambda: ["all black", "face mask", "hoodie up", "gloves at night"],
        description="Clothing patterns that indicate suspicious activity",
    )


class PromptConfigUnion(BaseModel):
    """Union type for model configurations."""

    nemotron: NemotronConfig | None = None
    florence2: Florence2Config | None = None
    yolo_world: YoloWorldConfig | None = None
    xclip: XClipConfig | None = None
    fashion_clip: FashionClipConfig | None = None


class PromptVersionInfo(BaseModel):
    """Version information for a prompt configuration."""

    model_config = ConfigDict(from_attributes=True)

    version: int = Field(..., ge=1, description="Version number (1-indexed)")
    created_at: datetime = Field(..., description="When this version was created")
    created_by: str = Field("system", description="Who created this version")
    description: str | None = Field(None, description="Optional description of changes")


class ModelPromptResponse(BaseModel):
    """Response for a single model's prompt configuration."""

    model_config = ConfigDict(from_attributes=True)

    model_name: str = Field(..., description="Name of the AI model")
    config: dict = Field(..., description="Current configuration for this model")
    version: int = Field(..., ge=1, description="Current version number")
    updated_at: datetime = Field(..., description="When last updated")


class AllPromptsResponse(BaseModel):
    """Response containing prompts for all models."""

    prompts: dict[str, ModelPromptResponse] = Field(
        ...,
        description="Dictionary mapping model names to their configurations",
    )


class PromptUpdateRequest(BaseModel):
    """Request to update a model's prompt configuration."""

    config: dict = Field(..., description="New configuration for the model")
    description: str | None = Field(None, description="Description of the changes")


class PromptUpdateResponse(BaseModel):
    """Response after updating a model's prompt."""

    model_name: str
    version: int
    message: str
    config: dict


class PromptTestRequest(BaseModel):
    """Request to test a modified prompt against an event."""

    model: str = Field(..., description="Model name to test (nemotron, florence2, etc.)")
    config: dict = Field(..., description="Modified configuration to test")
    event_id: int = Field(..., ge=1, description="Event ID to test against")


class PromptTestResultBefore(BaseModel):
    """Result from the original (current) prompt."""

    score: int = Field(..., ge=0, le=100, description="Risk score from original prompt")
    risk_level: str = Field(..., description="Risk level (low, medium, high, critical)")
    summary: str = Field(..., description="Summary from original analysis")


class PromptTestResultAfter(BaseModel):
    """Result from the modified prompt."""

    score: int = Field(..., ge=0, le=100, description="Risk score from modified prompt")
    risk_level: str = Field(..., description="Risk level (low, medium, high, critical)")
    summary: str = Field(..., description="Summary from modified analysis")


class PromptTestResponse(BaseModel):
    """Response from testing a modified prompt."""

    before: PromptTestResultBefore = Field(..., description="Results from original prompt")
    after: PromptTestResultAfter = Field(..., description="Results from modified prompt")
    improved: bool = Field(..., description="Whether the modification improved results")
    inference_time_ms: int = Field(..., ge=0, description="Time taken for inference in ms")


class PromptHistoryEntry(BaseModel):
    """A single entry in prompt version history."""

    model_config = ConfigDict(from_attributes=True)

    version: int = Field(..., ge=1, description="Version number")
    config: dict = Field(..., description="Configuration at this version")
    created_at: datetime = Field(..., description="When this version was created")
    created_by: str = Field("system", description="Who created this version")
    description: str | None = Field(None, description="Description of changes")


class PromptHistoryResponse(BaseModel):
    """Response containing version history for a model's prompts."""

    model_name: str
    versions: list[PromptHistoryEntry]
    total_versions: int


class PromptRestoreRequest(BaseModel):
    """Request to restore a specific version of a prompt."""

    description: str | None = Field(
        None,
        description="Optional description for the restore action",
    )


class PromptRestoreResponse(BaseModel):
    """Response after restoring a prompt version."""

    model_name: str
    restored_version: int
    new_version: int
    message: str


class PromptExportResponse(BaseModel):
    """Response containing all prompt configurations for export."""

    exported_at: datetime = Field(..., description="When the export was created")
    version: str = Field("1.0", description="Export format version")
    prompts: dict[str, dict] = Field(
        ...,
        description="All model configurations keyed by model name",
    )


class PromptImportRequest(BaseModel):
    """Request to import prompt configurations."""

    prompts: dict[str, dict] = Field(
        ...,
        description="Model configurations to import, keyed by model name",
    )
    overwrite: bool = Field(
        False,
        description="Whether to overwrite existing configurations",
    )


class PromptImportResponse(BaseModel):
    """Response after importing prompt configurations."""

    imported_count: int = Field(..., ge=0, description="Number of models imported")
    skipped_count: int = Field(..., ge=0, description="Number of models skipped")
    errors: list[str] = Field(default_factory=list, description="Any errors encountered")
    message: str


# =============================================================================
# Database-backed Prompt Config Schemas (for Playground Save functionality)
# =============================================================================


class PromptConfigRequest(BaseModel):
    """Request to update a model's prompt configuration (database-backed).

    Used by the Prompt Playground "Save" functionality to persist
    prompt configurations to the database.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    system_prompt: str = Field(
        ...,
        min_length=1,
        alias="systemPrompt",
        description="Full system prompt text for the model",
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="LLM temperature setting (0-2)",
    )
    max_tokens: int = Field(
        default=2048,
        ge=100,
        le=8192,
        alias="maxTokens",
        description="Maximum tokens in response (100-8192)",
    )


class PromptConfigResponse(BaseModel):
    """Response containing a model's prompt configuration (database-backed).

    Returned when retrieving or updating prompt configurations.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    model: str = Field(..., description="Model name")
    system_prompt: str = Field(
        ...,
        alias="systemPrompt",
        description="Full system prompt text for the model",
    )
    temperature: float = Field(..., description="LLM temperature setting (0-2)")
    max_tokens: int = Field(
        ...,
        alias="maxTokens",
        description="Maximum tokens in response (100-8192)",
    )
    version: int = Field(..., ge=1, description="Configuration version number")
    updated_at: datetime = Field(
        ...,
        alias="updatedAt",
        description="When the configuration was last updated",
    )


# =============================================================================
# A/B Testing Schemas (Prompt Playground)
# =============================================================================


class CustomTestPromptRequest(BaseModel):
    """Request to test a custom prompt against an existing event.

    This is used for A/B testing in the Prompt Playground - testing a
    modified prompt without persisting results to the database.
    """

    event_id: int = Field(..., ge=1, description="Event ID to test the prompt against")
    custom_prompt: str = Field(..., min_length=1, description="Custom prompt text to test")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="LLM temperature setting")
    max_tokens: int = Field(default=2048, ge=100, le=8192, description="Maximum tokens in response")
    model: str = Field(default="nemotron", description="Model name to use for testing")


class CustomTestPromptResponse(BaseModel):
    """Response from testing a custom prompt against an event.

    Results are NOT persisted - this is for A/B testing only.
    """

    risk_score: int = Field(..., ge=0, le=100, description="Computed risk score (0-100)")
    risk_level: str = Field(..., description="Risk level: low, medium, high, or critical")
    reasoning: str = Field(..., description="LLM reasoning for the risk assessment")
    summary: str = Field(..., description="Brief summary of the event analysis")
    entities: list[dict] = Field(
        default_factory=list, description="Detected entities in the analysis"
    )
    flags: list[dict] = Field(
        default_factory=list, description="Risk flags identified in the analysis"
    )
    recommended_action: str = Field(
        default="", description="Recommended action based on risk analysis"
    )
    processing_time_ms: int = Field(
        ..., ge=0, description="Time taken for inference in milliseconds"
    )
    tokens_used: int = Field(..., ge=0, description="Number of tokens used in inference")
