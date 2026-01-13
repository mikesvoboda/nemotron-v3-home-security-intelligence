"""Pydantic schemas for AI audit API endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ModelContributions(BaseModel):
    """Model contribution flags."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "rtdetr": True,
                "florence": True,
                "clip": False,
                "violence": False,
                "clothing": True,
                "vehicle": False,
                "pet": False,
                "weather": True,
                "image_quality": True,
                "zones": True,
                "baseline": False,
                "cross_camera": False,
            }
        }
    )

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

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "context_usage": 4.2,
                "reasoning_coherence": 4.5,
                "risk_justification": 3.8,
                "consistency": 4.0,
                "overall": 4.1,
            }
        }
    )

    context_usage: float | None = Field(None, ge=1, le=5)
    reasoning_coherence: float | None = Field(None, ge=1, le=5)
    risk_justification: float | None = Field(None, ge=1, le=5)
    consistency: float | None = Field(None, ge=1, le=5)
    overall: float | None = Field(None, ge=1, le=5)


class PromptImprovements(BaseModel):
    """Prompt improvement suggestions from self-evaluation."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "missing_context": ["Time since last motion event", "Weather conditions"],
                "confusing_sections": ["Zone overlap handling unclear"],
                "unused_data": ["Vehicle color data not utilized"],
                "format_suggestions": ["Add structured detection summary"],
                "model_gaps": ["Pet detection model not active"],
            }
        }
    )

    missing_context: list[str] = Field(default_factory=list)
    confusing_sections: list[str] = Field(default_factory=list)
    unused_data: list[str] = Field(default_factory=list)
    format_suggestions: list[str] = Field(default_factory=list)
    model_gaps: list[str] = Field(default_factory=list)


class EventAuditResponse(BaseModel):
    """Full audit response for a single event."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 456,
                "event_id": 12345,
                "audited_at": "2026-01-03T10:30:00Z",
                "is_fully_evaluated": True,
                "contributions": {
                    "rtdetr": True,
                    "florence": True,
                    "clip": False,
                    "violence": False,
                    "clothing": True,
                    "vehicle": False,
                    "pet": False,
                    "weather": True,
                    "image_quality": True,
                    "zones": True,
                    "baseline": False,
                    "cross_camera": False,
                },
                "prompt_length": 2048,
                "prompt_token_estimate": 512,
                "enrichment_utilization": 0.85,
                "scores": {
                    "context_usage": 4.2,
                    "reasoning_coherence": 4.5,
                    "risk_justification": 3.8,
                    "consistency": 4.0,
                    "overall": 4.1,
                },
                "consistency_risk_score": 62,
                "consistency_diff": 3,
                "self_eval_critique": "More historical context would improve analysis.",
                "improvements": {
                    "missing_context": ["Time since last motion event"],
                    "confusing_sections": [],
                    "unused_data": [],
                    "format_suggestions": [],
                    "model_gaps": [],
                },
            }
        },
    )

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

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_events": 1250,
                "audited_events": 1100,
                "fully_evaluated_events": 950,
                "avg_quality_score": 4.1,
                "avg_consistency_rate": 0.92,
                "avg_enrichment_utilization": 0.78,
                "model_contribution_rates": {
                    "rtdetr": 0.98,
                    "florence": 0.85,
                    "clothing": 0.72,
                    "weather": 0.95,
                },
                "audits_by_day": [
                    {"date": "2026-01-01", "count": 45},
                    {"date": "2026-01-02", "count": 52},
                    {"date": "2026-01-03", "count": 38},
                ],
            }
        }
    )

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

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "model_name": "florence",
                "contribution_rate": 0.85,
                "quality_correlation": 0.72,
                "event_count": 1050,
            }
        }
    )

    model_name: str
    contribution_rate: float
    quality_correlation: float | None
    event_count: int


class LeaderboardResponse(BaseModel):
    """Model leaderboard response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "entries": [
                    {
                        "model_name": "rtdetr",
                        "contribution_rate": 0.98,
                        "quality_correlation": 0.85,
                        "event_count": 1200,
                    },
                    {
                        "model_name": "florence",
                        "contribution_rate": 0.85,
                        "quality_correlation": 0.72,
                        "event_count": 1050,
                    },
                ],
                "period_days": 30,
            }
        }
    )

    entries: list[ModelLeaderboardEntry]
    period_days: int


class RecommendationItem(BaseModel):
    """Single recommendation item."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "category": "missing_context",
                "suggestion": "Add time since last motion event to prompt",
                "frequency": 25,
                "priority": "high",
            }
        }
    )

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

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "recommendations": [
                    {
                        "category": "missing_context",
                        "suggestion": "Add time since last motion event",
                        "frequency": 25,
                        "priority": "high",
                    },
                    {
                        "category": "model_gaps",
                        "suggestion": "Enable pet detection model",
                        "frequency": 12,
                        "priority": "medium",
                    },
                ],
                "total_events_analyzed": 500,
            }
        }
    )

    recommendations: list[RecommendationItem]
    total_events_analyzed: int


class BatchAuditRequest(BaseModel):
    """Request for batch audit processing."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "limit": 100,
                "min_risk_score": 50,
                "force_reevaluate": False,
            }
        }
    )

    limit: int = Field(100, ge=1, le=1000)
    min_risk_score: int | None = Field(None, ge=0, le=100)
    force_reevaluate: bool = False


class BatchAuditResponse(BaseModel):
    """Response for batch audit request (legacy synchronous response)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "queued_count": 75,
                "message": "Queued 75 events for audit processing",
            }
        }
    )

    queued_count: int
    message: str


class BatchAuditJobResponse(BaseModel):
    """Response for async batch audit job creation.

    Returned immediately when triggering a batch audit, containing
    the job ID for progress tracking via GET /api/ai-audit/batch/{job_id}.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "pending",
                "message": "Batch audit job created. Use GET /api/ai-audit/batch/550e8400-e29b-41d4-a716-446655440000 to track progress.",
                "total_events": 75,
            }
        }
    )

    job_id: str = Field(..., description="Unique job ID for tracking progress")
    status: str = Field(..., description="Initial job status (pending)")
    message: str = Field(..., description="Human-readable status message")
    total_events: int = Field(..., ge=0, description="Number of events queued for processing")


class BatchAuditJobStatusResponse(BaseModel):
    """Response for batch audit job status query.

    Provides detailed progress information for an ongoing or completed
    batch audit job.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "running",
                "progress": 45,
                "message": "Processing event 45 of 100",
                "total_events": 100,
                "processed_events": 45,
                "failed_events": 2,
                "created_at": "2026-01-03T10:30:00Z",
                "started_at": "2026-01-03T10:30:01Z",
                "completed_at": None,
                "error": None,
            }
        }
    )

    job_id: str = Field(..., description="Unique job ID")
    status: str = Field(..., description="Current job status (pending, running, completed, failed)")
    progress: int = Field(..., ge=0, le=100, description="Progress percentage (0-100)")
    message: str | None = Field(None, description="Current status message")
    total_events: int = Field(..., ge=0, description="Total events to process")
    processed_events: int = Field(..., ge=0, description="Events successfully processed")
    failed_events: int = Field(0, ge=0, description="Events that failed processing")
    created_at: datetime = Field(..., description="When the job was created")
    started_at: datetime | None = Field(None, description="When processing started")
    completed_at: datetime | None = Field(None, description="When processing completed")
    error: str | None = Field(None, description="Error message if job failed")


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

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "system_prompt": "You are a home security AI assistant analyzing camera detections...",
                "temperature": 0.7,
                "max_tokens": 2048,
            }
        }
    )

    system_prompt: str = Field(..., description="Full system prompt text for risk analysis")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="LLM temperature setting")
    max_tokens: int = Field(2048, ge=100, le=8192, description="Maximum tokens in response")


class Florence2Config(BaseModel):
    """Configuration for Florence-2 VQA model."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "vqa_queries": [
                    "What is this person wearing?",
                    "Is this person carrying anything?",
                    "What color is the vehicle?",
                ]
            }
        }
    )

    vqa_queries: list[str] = Field(
        ...,
        description="List of visual question-answering queries",
        min_length=1,
    )


class YoloWorldConfig(BaseModel):
    """Configuration for YOLO-World object detection."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "object_classes": ["person", "car", "truck", "bicycle", "dog", "cat"],
                "confidence_threshold": 0.5,
            }
        }
    )

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

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "action_classes": [
                    "walking",
                    "running",
                    "standing",
                    "sitting",
                    "driving",
                    "entering",
                ]
            }
        }
    )

    action_classes: list[str] = Field(
        ...,
        description="List of action classes to recognize",
        min_length=1,
    )


class FashionClipConfig(BaseModel):
    """Configuration for FashionCLIP clothing analysis."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "clothing_categories": ["jacket", "shirt", "pants", "shorts", "dress", "hat"],
                "suspicious_indicators": [
                    "all black",
                    "face mask",
                    "hoodie up",
                    "gloves at night",
                ],
            }
        }
    )

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

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "nemotron": {
                    "system_prompt": "You are a home security AI...",
                    "temperature": 0.7,
                    "max_tokens": 2048,
                },
                "florence2": None,
                "yolo_world": None,
                "xclip": None,
                "fashion_clip": None,
            }
        }
    )

    nemotron: NemotronConfig | None = None
    florence2: Florence2Config | None = None
    yolo_world: YoloWorldConfig | None = None
    xclip: XClipConfig | None = None
    fashion_clip: FashionClipConfig | None = None


class PromptVersionInfo(BaseModel):
    """Version information for a prompt configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "version": 3,
                "created_at": "2026-01-03T10:30:00Z",
                "created_by": "admin",
                "description": "Added weather context to prompt",
            }
        },
    )

    version: int = Field(..., ge=1, description="Version number (1-indexed)")
    created_at: datetime = Field(..., description="When this version was created")
    created_by: str = Field("system", description="Who created this version")
    description: str | None = Field(None, description="Optional description of changes")


class ModelPromptResponse(BaseModel):
    """Response for a single model's prompt configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "model_name": "nemotron",
                "config": {
                    "system_prompt": "You are a home security AI...",
                    "temperature": 0.7,
                    "max_tokens": 2048,
                },
                "version": 3,
                "updated_at": "2026-01-03T10:30:00Z",
            }
        },
    )

    model_name: str = Field(..., description="Name of the AI model")
    config: dict = Field(..., description="Current configuration for this model")
    version: int = Field(..., ge=1, description="Current version number")
    updated_at: datetime = Field(..., description="When last updated")


class AllPromptsResponse(BaseModel):
    """Response containing prompts for all models."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "prompts": {
                    "nemotron": {
                        "model_name": "nemotron",
                        "config": {"system_prompt": "...", "temperature": 0.7},
                        "version": 3,
                        "updated_at": "2026-01-03T10:30:00Z",
                    },
                    "florence2": {
                        "model_name": "florence2",
                        "config": {"vqa_queries": ["What is this?"]},
                        "version": 1,
                        "updated_at": "2026-01-01T08:00:00Z",
                    },
                }
            }
        }
    )

    prompts: dict[str, ModelPromptResponse] = Field(
        ...,
        description="Dictionary mapping model names to their configurations",
    )


class PromptUpdateRequest(BaseModel):
    """Request to update a model's prompt configuration."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "config": {
                    "system_prompt": "Updated system prompt with new context...",
                    "temperature": 0.8,
                    "max_tokens": 2048,
                },
                "description": "Added weather context to improve analysis",
            }
        }
    )

    config: dict = Field(..., description="New configuration for the model")
    description: str | None = Field(None, description="Description of the changes")


class PromptUpdateResponse(BaseModel):
    """Response after updating a model's prompt."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "model_name": "nemotron",
                "version": 4,
                "message": "Prompt configuration updated successfully",
                "config": {
                    "system_prompt": "Updated system prompt...",
                    "temperature": 0.8,
                    "max_tokens": 2048,
                },
            }
        }
    )

    model_name: str
    version: int
    message: str
    config: dict


class PromptTestRequest(BaseModel):
    """Request to test a modified prompt against an event."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "model": "nemotron",
                "config": {
                    "system_prompt": "Modified prompt for testing...",
                    "temperature": 0.7,
                    "max_tokens": 2048,
                },
                "event_id": 12345,
            }
        }
    )

    model: str = Field(..., description="Model name to test (nemotron, florence2, etc.)")
    config: dict = Field(..., description="Modified configuration to test")
    event_id: int = Field(..., ge=1, description="Event ID to test against")


class PromptTestResultBefore(BaseModel):
    """Result from the original (current) prompt."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "score": 65,
                "risk_level": "medium",
                "summary": "Person detected at front door during evening hours",
            }
        }
    )

    score: int = Field(..., ge=0, le=100, description="Risk score from original prompt")
    risk_level: str = Field(..., description="Risk level (low, medium, high, critical)")
    summary: str = Field(..., description="Summary from original analysis")


class PromptTestResultAfter(BaseModel):
    """Result from the modified prompt."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "score": 45,
                "risk_level": "low",
                "summary": "Regular visitor detected - matches known delivery pattern",
            }
        }
    )

    score: int = Field(..., ge=0, le=100, description="Risk score from modified prompt")
    risk_level: str = Field(..., description="Risk level (low, medium, high, critical)")
    summary: str = Field(..., description="Summary from modified analysis")


class PromptTestResponse(BaseModel):
    """Response from testing a modified prompt."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "before": {
                    "score": 65,
                    "risk_level": "medium",
                    "summary": "Person detected at front door during evening hours",
                },
                "after": {
                    "score": 45,
                    "risk_level": "low",
                    "summary": "Regular visitor detected - matches known delivery pattern",
                },
                "improved": True,
                "inference_time_ms": 1250,
            }
        }
    )

    before: PromptTestResultBefore = Field(..., description="Results from original prompt")
    after: PromptTestResultAfter = Field(..., description="Results from modified prompt")
    improved: bool = Field(..., description="Whether the modification improved results")
    inference_time_ms: int = Field(..., ge=0, description="Time taken for inference in ms")


class PromptHistoryEntry(BaseModel):
    """A single entry in prompt version history."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "version": 2,
                "config": {
                    "system_prompt": "Previous version of prompt...",
                    "temperature": 0.7,
                    "max_tokens": 2048,
                },
                "created_at": "2026-01-02T14:00:00Z",
                "created_by": "admin",
                "description": "Initial prompt configuration",
            }
        },
    )

    version: int = Field(..., ge=1, description="Version number")
    config: dict = Field(..., description="Configuration at this version")
    created_at: datetime = Field(..., description="When this version was created")
    created_by: str = Field("system", description="Who created this version")
    description: str | None = Field(None, description="Description of changes")


class PromptHistoryResponse(BaseModel):
    """Response containing version history for a model's prompts."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "model_name": "nemotron",
                "versions": [
                    {
                        "version": 3,
                        "config": {"system_prompt": "...", "temperature": 0.8},
                        "created_at": "2026-01-03T10:30:00Z",
                        "created_by": "admin",
                        "description": "Added weather context",
                    },
                    {
                        "version": 2,
                        "config": {"system_prompt": "...", "temperature": 0.7},
                        "created_at": "2026-01-02T14:00:00Z",
                        "created_by": "system",
                        "description": "Initial configuration",
                    },
                ],
                "total_versions": 3,
            }
        }
    )

    model_name: str
    versions: list[PromptHistoryEntry]
    total_versions: int


class PromptRestoreRequest(BaseModel):
    """Request to restore a specific version of a prompt."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "description": "Restoring to version 2 due to regression in analysis quality",
            }
        }
    )

    description: str | None = Field(
        None,
        description="Optional description for the restore action",
    )


class PromptRestoreResponse(BaseModel):
    """Response after restoring a prompt version."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "model_name": "nemotron",
                "restored_version": 2,
                "new_version": 4,
                "message": "Successfully restored version 2 as new version 4",
            }
        }
    )

    model_name: str
    restored_version: int
    new_version: int
    message: str


class PromptExportResponse(BaseModel):
    """Response containing all prompt configurations for export."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "exported_at": "2026-01-03T10:30:00Z",
                "version": "1.0",
                "prompts": {
                    "nemotron": {
                        "system_prompt": "You are a home security AI...",
                        "temperature": 0.7,
                        "max_tokens": 2048,
                    },
                    "florence2": {
                        "vqa_queries": ["What is this person wearing?"],
                    },
                },
            }
        }
    )

    exported_at: datetime = Field(..., description="When the export was created")
    version: str = Field("1.0", description="Export format version")
    prompts: dict[str, dict] = Field(
        ...,
        description="All model configurations keyed by model name",
    )


class PromptImportRequest(BaseModel):
    """Request to import prompt configurations."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "prompts": {
                    "nemotron": {
                        "system_prompt": "Imported system prompt...",
                        "temperature": 0.7,
                        "max_tokens": 2048,
                    },
                },
                "overwrite": True,
            }
        }
    )

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

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "imported_count": 3,
                "skipped_count": 1,
                "errors": [],
                "message": "Successfully imported 3 prompt configurations",
            }
        }
    )

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

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "systemPrompt": "You are a home security AI assistant...",
                "temperature": 0.7,
                "maxTokens": 2048,
            }
        },
    )

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

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "model": "nemotron",
                "systemPrompt": "You are a home security AI assistant...",
                "temperature": 0.7,
                "maxTokens": 2048,
                "version": 3,
                "updatedAt": "2026-01-03T10:30:00Z",
            }
        },
    )

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

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_id": 12345,
                "custom_prompt": "You are a home security AI with enhanced context...",
                "temperature": 0.7,
                "max_tokens": 2048,
                "model": "nemotron",
            }
        }
    )

    event_id: int = Field(..., ge=1, description="Event ID to test the prompt against")
    custom_prompt: str = Field(..., min_length=1, description="Custom prompt text to test")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="LLM temperature setting")
    max_tokens: int = Field(default=2048, ge=100, le=8192, description="Maximum tokens in response")
    model: str = Field(default="nemotron", description="Model name to use for testing")


class CustomTestPromptResponse(BaseModel):
    """Response from testing a custom prompt against an event.

    Results are NOT persisted - this is for A/B testing only.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "risk_score": 45,
                "risk_level": "low",
                "reasoning": "The detected person matches the expected delivery pattern based on time and approach direction.",
                "summary": "Delivery person detected at front door during expected hours",
                "entities": [{"type": "person", "confidence": 0.95}],
                "flags": [],
                "recommended_action": "No action required",
                "processing_time_ms": 1250,
                "tokens_used": 512,
            }
        }
    )

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
