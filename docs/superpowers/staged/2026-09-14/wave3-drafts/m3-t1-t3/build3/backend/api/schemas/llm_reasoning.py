"""Pydantic schemas for LLM Reasoning Explorer API endpoints.

These schemas expose LLMInteraction data including:
- Think blocks from raw_response
- Enrichment sources from enrichment_snapshot
- Context sources tracking
- Truncation indicators
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EnrichmentSource(BaseModel):
    """Source of enrichment data that was used in analysis."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "florence",
                "populated": True,
                "field_count": 5,
                "sample_fields": ["scene_description", "detected_objects", "activities"],
            }
        }
    )

    name: str = Field(..., description="Name of the enrichment source/model")
    populated: bool = Field(..., description="Whether this source provided data")
    field_count: int = Field(0, ge=0, description="Number of fields populated by this source")
    sample_fields: list[str] = Field(
        default_factory=list,
        description="Sample field names from this source",
    )


class TruncationInfo(BaseModel):
    """Information about what context was truncated due to token limits."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "was_truncated": True,
                "original_length": 8500,
                "truncated_length": 4096,
                "dropped_sections": ["historical_events", "distant_camera_correlations"],
                "truncation_reason": "Token limit exceeded (max: 4096)",
            }
        }
    )

    was_truncated: bool = Field(False, description="Whether any context was truncated")
    original_length: int | None = Field(None, ge=0, description="Original context length in tokens")
    truncated_length: int | None = Field(None, ge=0, description="Final context length in tokens")
    dropped_sections: list[str] = Field(
        default_factory=list,
        description="Names of sections that were dropped/truncated",
    )
    truncation_reason: str | None = Field(None, description="Reason for truncation")


class ReasoningStep(BaseModel):
    """A single reasoning step extracted from think blocks."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "step_number": 1,
                "content": "Analyzing the detected person's behavior...",
                "key_factors": ["proximity to entrance", "time of day", "previous activity"],
                "confidence_indicator": "high",
            }
        }
    )

    step_number: int = Field(..., ge=1, description="Sequential step number")
    content: str = Field(..., description="The reasoning content for this step")
    key_factors: list[str] = Field(
        default_factory=list,
        description="Key factors identified in this reasoning step",
    )
    confidence_indicator: str | None = Field(
        None,
        description="Confidence level mentioned in this step (high/medium/low)",
    )


class ThinkBlockContent(BaseModel):
    """Parsed content from <think> blocks in LLM response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "raw_think_block": "<think>First, I observe that...",
                "reasoning_steps": [
                    {
                        "step_number": 1,
                        "content": "Analyzing the detected person's behavior...",
                        "key_factors": ["proximity to entrance"],
                        "confidence_indicator": "high",
                    }
                ],
                "key_observations": ["Person approaching door", "No vehicle visible"],
                "risk_factors_mentioned": ["Late night hour", "Unknown individual"],
            }
        }
    )

    raw_think_block: str | None = Field(None, description="Raw content of <think> block")
    reasoning_steps: list[ReasoningStep] = Field(
        default_factory=list,
        description="Parsed reasoning steps from the think block",
    )
    key_observations: list[str] = Field(
        default_factory=list,
        description="Key observations extracted from reasoning",
    )
    risk_factors_mentioned: list[str] = Field(
        default_factory=list,
        description="Risk factors explicitly mentioned in reasoning",
    )


class HouseholdMatch(BaseModel):
    """A matched household member from the analysis."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "entity_type": "person",
                "entity_name": "John Doe",
                "similarity_score": 0.92,
                "match_method": "face_recognition",
            }
        }
    )

    entity_type: str = Field(..., description="Type of entity (person, vehicle, pet)")
    entity_name: str | None = Field(None, description="Name of matched entity if available")
    similarity_score: float = Field(..., ge=0, le=1, description="Similarity score (0-1)")
    match_method: str | None = Field(None, description="Method used for matching")


class LLMReasoningResponse(BaseModel):
    """Full LLM reasoning explorer response for an event."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 123,
                "event_id": 456,
                "created_at": "2026-01-15T10:30:00Z",
                "raw_response": "Based on the analysis...",
                "parsed_response": {
                    "risk_score": 72,
                    "risk_level": "medium",
                    "summary": "Unknown person loitering near entry point.",
                    "reasoning": "Prolonged presence and repeated approach patterns increase risk.",
                },
                "think_block": {
                    "raw_think_block": "<think>First, I observe...",
                    "reasoning_steps": [],
                    "key_observations": [],
                    "risk_factors_mentioned": [],
                },
                "enrichment_sources": [
                    {"name": "florence", "populated": True, "field_count": 5},
                ],
                "truncation_info": {"was_truncated": False},
                "household_matches": [],
                "debug_info": {
                    "prompt_length": 2048,
                    "enrichment_snapshot_keys": ["florence", "clip", "weather"],
                },
            }
        },
    )

    id: int = Field(..., description="LLM interaction record ID")
    event_id: int = Field(..., description="Associated event ID")
    created_at: datetime = Field(..., description="When the analysis occurred")

    # Raw response for debug mode
    raw_response: str = Field(..., description="Full raw LLM response")
    parsed_response: dict[str, Any] | None = Field(
        None,
        description="Parsed JSON response when raw_response is valid JSON",
    )

    # Parsed think block content
    think_block: ThinkBlockContent = Field(
        default_factory=ThinkBlockContent,
        description="Parsed content from <think> blocks",
    )

    # Enrichment sources summary
    enrichment_sources: list[EnrichmentSource] = Field(
        default_factory=list,
        description="Sources that contributed enrichment data",
    )

    # Truncation information
    truncation_info: TruncationInfo = Field(
        default_factory=TruncationInfo,
        description="Information about context truncation",
    )

    # Household matches
    household_matches: list[HouseholdMatch] = Field(
        default_factory=list,
        description="Matched household members/vehicles",
    )

    # Debug information (prompt inspection)
    debug_info: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional debug information for prompt inspection",
    )


class LLMReasoningNotFoundResponse(BaseModel):
    """Response when no LLM reasoning data is available for an event."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_id": 456,
                "message": "No LLM reasoning data available for this event",
                "reason": "Event was processed before LLM interaction tracking was enabled",
            }
        }
    )

    event_id: int = Field(..., description="The event ID that was queried")
    message: str = Field(..., description="Human-readable message")
    reason: str | None = Field(None, description="Reason why reasoning data is not available")
