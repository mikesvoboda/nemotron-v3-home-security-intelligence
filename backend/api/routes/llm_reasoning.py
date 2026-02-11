"""API routes for LLM Reasoning Explorer.

This module exposes LLMInteraction data for debugging and transparency:
- Think blocks from raw_response
- Enrichment sources that fed into analysis
- Truncation indicators
- Prompt inspection in debug mode

Part of NEM-5024: Hidden Backend Exposure epic.
"""

import json
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import ORJSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.api.dependencies import get_event_or_404
from backend.api.schemas.llm_reasoning import (
    EnrichmentSource,
    HouseholdMatch,
    LLMReasoningNotFoundResponse,
    LLMReasoningResponse,
    ReasoningStep,
    ThinkBlockContent,
    TruncationInfo,
)
from backend.core.database import get_read_db
from backend.core.logging import get_logger
from backend.models.event import Event
from backend.models.llm_interaction import LLMInteraction

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/llm-reasoning",
    tags=["llm-reasoning"],
    default_response_class=ORJSONResponse,
)


def _extract_think_block(raw_response: str) -> str | None:
    """Extract content from <think>...</think> blocks in raw response.

    Args:
        raw_response: The full LLM response text

    Returns:
        Extracted think block content or None if not found
    """
    # Match <think>...</think> blocks (case-insensitive, multiline)
    pattern = r"<think>(.*?)</think>"
    match = re.search(pattern, raw_response, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def _parse_json_response(raw_response: str) -> dict[str, Any] | None:
    """Parse raw LLM response when it's structured JSON."""
    try:
        parsed = json.loads(raw_response)
    except (json.JSONDecodeError, TypeError):
        return None
    if isinstance(parsed, dict):
        return parsed
    return None


def _parse_reasoning_steps(think_content: str) -> list[ReasoningStep]:
    """Parse think block content into structured reasoning steps.

    Attempts to identify numbered steps, bullet points, or paragraph breaks
    to segment reasoning into steps.

    Args:
        think_content: Raw content from think block

    Returns:
        List of ReasoningStep objects
    """
    steps: list[ReasoningStep] = []

    # Try to find numbered steps (1. 2. 3. or 1) 2) 3))
    numbered_pattern = r"(?:^|\n)\s*(\d+)[.)]\s*(.+?)(?=\n\s*\d+[.)]|\Z)"
    numbered_matches = re.findall(numbered_pattern, think_content, re.DOTALL)

    if numbered_matches:
        for num_str, raw_content in numbered_matches:
            step_num = int(num_str)
            cleaned_content = raw_content.strip()
            if cleaned_content:
                steps.append(
                    ReasoningStep(
                        step_number=step_num,
                        content=cleaned_content,
                        key_factors=_extract_key_factors(cleaned_content),
                        confidence_indicator=_extract_confidence(cleaned_content),
                    )
                )
        return steps

    # Fall back to paragraph-based splitting
    paragraphs = [p.strip() for p in think_content.split("\n\n") if p.strip()]
    for i, para in enumerate(paragraphs, 1):
        steps.append(
            ReasoningStep(
                step_number=i,
                content=para,
                key_factors=_extract_key_factors(para),
                confidence_indicator=_extract_confidence(para),
            )
        )

    # If still no steps, treat entire content as one step
    if not steps and think_content.strip():
        steps.append(
            ReasoningStep(
                step_number=1,
                content=think_content.strip(),
                key_factors=_extract_key_factors(think_content),
                confidence_indicator=_extract_confidence(think_content),
            )
        )

    return steps


def _extract_key_factors(content: str) -> list[str]:
    """Extract key factors mentioned in reasoning content.

    Looks for common patterns indicating factors:
    - "due to X"
    - "because of X"
    - "factor: X"
    - "considering X"

    Args:
        content: Text to extract factors from

    Returns:
        List of identified key factors
    """
    factors: list[str] = []

    patterns = [
        r"due to\s+([^,.]+)",
        r"because of\s+([^,.]+)",
        r"considering\s+([^,.]+)",
        r"factor:\s*([^,.]+)",
        r"based on\s+([^,.]+)",
        r"given that\s+([^,.]+)",
        r"indicates?\s+([^,.]+)",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        for match in matches:
            factor = match.strip()
            if factor and len(factor) > 3 and factor not in factors:
                factors.append(factor)

    # Limit to avoid noise
    return factors[:5]


def _extract_confidence(content: str) -> str | None:
    """Extract confidence indicator from content.

    Args:
        content: Text to analyze

    Returns:
        Confidence level (high/medium/low) or None
    """
    content_lower = content.lower()

    # Check low indicators FIRST since they are more specific
    # e.g., "uncertain" should not be overridden by "confident" matching "am confident"
    low_indicators = ["low confidence", "uncertain", "unclear", "possibly", "might be"]
    high_indicators = ["high confidence", "confident", "certain", "clearly", "definitely"]
    medium_indicators = ["moderate confidence", "likely", "probably", "suggests"]

    for indicator in low_indicators:
        if indicator in content_lower:
            return "low"

    for indicator in high_indicators:
        if indicator in content_lower:
            return "high"

    for indicator in medium_indicators:
        if indicator in content_lower:
            return "medium"

    return None


def _extract_key_observations(think_content: str) -> list[str]:
    """Extract key observations from think block content.

    Looks for observation patterns like:
    - "I observe/notice/see..."
    - Sentences starting with "The detected..."

    Args:
        think_content: Raw think block content

    Returns:
        List of key observations
    """
    observations: list[str] = []

    patterns = [
        r"I (?:observe|notice|see|note)\s+that\s+([^.]+)",
        r"(?:^|\n)The detected\s+([^.]+)",
        r"observation:\s*([^.]+)",
        r"(?:^|\n)There (?:is|are)\s+([^.]+)",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, think_content, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            obs = match.strip()
            if obs and len(obs) > 5 and obs not in observations:
                observations.append(obs)

    return observations[:10]


def _extract_risk_factors(think_content: str) -> list[str]:
    """Extract risk factors explicitly mentioned in reasoning.

    Args:
        think_content: Raw think block content

    Returns:
        List of risk factors
    """
    risk_factors: list[str] = []

    # Common risk-related keywords
    risk_patterns = [
        r"risk factor[s]?:\s*([^.]+)",
        r"(?:increases?|raises?)\s+(?:the\s+)?risk\s+(?:because|due to)\s+([^.]+)",
        r"suspicious\s+(?:because|due to)\s+([^.]+)",
        r"concerning\s+(?:because|due to)\s+([^.]+)",
        r"threat\s+(?:from|due to)\s+([^.]+)",
    ]

    for pattern in risk_patterns:
        matches = re.findall(pattern, think_content, re.IGNORECASE)
        for match in matches:
            factor = match.strip()
            if factor and factor not in risk_factors:
                risk_factors.append(factor)

    # Also look for keywords
    keywords = [
        "late night",
        "unusual time",
        "unknown person",
        "unrecognized",
        "suspicious behavior",
        "loitering",
        "approaching",
        "multiple attempts",
        "concealed",
        "obscured face",
    ]

    content_lower = think_content.lower()
    for kw in keywords:
        if kw in content_lower and kw not in risk_factors:
            risk_factors.append(kw)

    return risk_factors[:10]


def _parse_enrichment_sources(enrichment_snapshot: dict[str, Any]) -> list[EnrichmentSource]:
    """Parse enrichment snapshot into source summaries.

    Args:
        enrichment_snapshot: The frozen enrichment data from LLMInteraction

    Returns:
        List of EnrichmentSource objects
    """
    sources: list[EnrichmentSource] = []

    # Known enrichment source categories
    known_sources = {
        "florence": "Florence-2 Vision Analysis",
        "clip": "CLIP Embeddings",
        "weather": "Weather Analysis",
        "violence": "Violence Detection",
        "clothing": "Clothing Analysis",
        "vehicle": "Vehicle Classification",
        "pet": "Pet Detection",
        "pose": "Pose Estimation",
        "demographics": "Demographics Analysis",
        "image_quality": "Image Quality Assessment",
        "zones": "Zone Analysis",
        "baseline": "Baseline Comparison",
        "cross_camera": "Cross-Camera Correlation",
        "detections": "Object Detections",
    }

    for key, display_name in known_sources.items():
        if key in enrichment_snapshot:
            data = enrichment_snapshot[key]
            populated = bool(data)
            field_count = 0
            sample_fields: list[str] = []

            if isinstance(data, dict):
                field_count = len(data)
                sample_fields = list(data.keys())[:5]
            elif isinstance(data, list):
                field_count = len(data)
                if data and isinstance(data[0], dict):
                    sample_fields = list(data[0].keys())[:5]

            sources.append(
                EnrichmentSource(
                    name=display_name,
                    populated=populated,
                    field_count=field_count,
                    sample_fields=sample_fields,
                )
            )

    # Add any unknown sources from the snapshot
    for key, data in enrichment_snapshot.items():
        if key not in known_sources:
            populated = bool(data)
            field_count = 0
            sample_fields = []

            if isinstance(data, dict):
                field_count = len(data)
                sample_fields = list(data.keys())[:5]
            elif isinstance(data, list):
                field_count = len(data)

            sources.append(
                EnrichmentSource(
                    name=key.replace("_", " ").title(),
                    populated=populated,
                    field_count=field_count,
                    sample_fields=sample_fields,
                )
            )

    return sources


def _parse_truncation_info(truncation_log: dict[str, Any] | None) -> TruncationInfo:
    """Parse truncation log into structured info.

    Args:
        truncation_log: The truncation log from LLMInteraction

    Returns:
        TruncationInfo object
    """
    if not truncation_log:
        return TruncationInfo(was_truncated=False)

    return TruncationInfo(
        was_truncated=truncation_log.get("was_truncated", False),
        original_length=truncation_log.get("original_length"),
        truncated_length=truncation_log.get("truncated_length"),
        dropped_sections=truncation_log.get("dropped_sections", []),
        truncation_reason=truncation_log.get("reason"),
    )


def _parse_household_matches(household_matches: dict[str, Any] | None) -> list[HouseholdMatch]:
    """Parse household matches into structured list.

    Args:
        household_matches: The household matches from LLMInteraction

    Returns:
        List of HouseholdMatch objects
    """
    if not household_matches:
        return []

    matches: list[HouseholdMatch] = []

    # Handle list of matches
    if isinstance(household_matches, list):
        for match in household_matches:
            if isinstance(match, dict):
                matches.append(
                    HouseholdMatch(
                        entity_type=match.get("entity_type", "unknown"),
                        entity_name=match.get("entity_name") or match.get("name"),
                        similarity_score=match.get("similarity_score", 0.0),
                        match_method=match.get("match_method"),
                    )
                )

    # Handle dict with entity types as keys
    elif isinstance(household_matches, dict):
        for entity_type, match_data in household_matches.items():
            if isinstance(match_data, list):
                for item in match_data:
                    if isinstance(item, dict):
                        matches.append(
                            HouseholdMatch(
                                entity_type=entity_type,
                                entity_name=item.get("name") or item.get("entity_name"),
                                similarity_score=item.get(
                                    "similarity", item.get("similarity_score", 0.0)
                                ),
                                match_method=item.get("method") or item.get("match_method"),
                            )
                        )
            elif isinstance(match_data, dict):
                matches.append(
                    HouseholdMatch(
                        entity_type=entity_type,
                        entity_name=match_data.get("name") or match_data.get("entity_name"),
                        similarity_score=match_data.get(
                            "similarity", match_data.get("similarity_score", 0.0)
                        ),
                        match_method=match_data.get("method") or match_data.get("match_method"),
                    )
                )

    return matches


@router.get(
    "/events/{event_id}",
    response_model=LLMReasoningResponse,
    responses={
        404: {
            "model": LLMReasoningNotFoundResponse,
            "description": "Event not found or no LLM reasoning data available",
        },
        500: {"description": "Internal server error"},
    },
)
async def get_llm_reasoning(
    event_id: int,
    include_debug: bool = Query(
        False,
        description="Include debug information for prompt inspection",
    ),
    db: AsyncSession = Depends(get_read_db),
) -> LLMReasoningResponse:
    """Get LLM reasoning data for a specific event.

    Returns the full LLM interaction record including:
    - Parsed <think> blocks with reasoning steps
    - Enrichment sources that contributed to analysis
    - Truncation information (what context was dropped)
    - Household matches with similarity scores
    - Debug information for prompt inspection (when enabled)

    Args:
        event_id: The event ID to fetch reasoning for
        include_debug: Whether to include debug information
        db: Database session

    Returns:
        LLMReasoningResponse with full reasoning data

    Raises:
        HTTPException: 404 if event or LLM reasoning not found
    """
    # Verify event exists
    await get_event_or_404(event_id, db)

    # Fetch LLM interaction for this event
    query = select(LLMInteraction).where(LLMInteraction.event_id == event_id)
    result = await db.execute(query)
    interaction = result.scalar_one_or_none()

    if not interaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "event_id": event_id,
                "message": "No LLM reasoning data available for this event",
                "reason": "Event may have been processed before LLM interaction tracking was enabled",
            },
        )

    # Parse response: prefer explicit <think> block, fall back to JSON reasoning field.
    parsed_response = _parse_json_response(interaction.raw_response)
    think_block_raw = _extract_think_block(interaction.raw_response)
    if not think_block_raw and parsed_response:
        parsed_reasoning = parsed_response.get("reasoning")
        if isinstance(parsed_reasoning, str) and parsed_reasoning.strip():
            think_block_raw = parsed_reasoning.strip()

    think_block = ThinkBlockContent(
        raw_think_block=think_block_raw,
        reasoning_steps=_parse_reasoning_steps(think_block_raw) if think_block_raw else [],
        key_observations=_extract_key_observations(think_block_raw) if think_block_raw else [],
        risk_factors_mentioned=_extract_risk_factors(think_block_raw) if think_block_raw else [],
    )

    # Parse enrichment sources
    enrichment_sources = _parse_enrichment_sources(interaction.enrichment_snapshot or {})

    # Parse truncation info
    truncation_info = _parse_truncation_info(interaction.truncation_log)

    # Parse household matches
    household_matches = _parse_household_matches(interaction.household_matches)

    # Build debug info
    debug_info: dict[str, Any] = {}
    if include_debug:
        debug_info = {
            "prompt_length": len(interaction.raw_response) if interaction.raw_response else 0,
            "enrichment_snapshot_keys": list((interaction.enrichment_snapshot or {}).keys()),
            "context_sources": interaction.context_sources,
            "validation_result": interaction.validation_result,
            "has_truncation_log": interaction.truncation_log is not None,
            "has_household_matches": interaction.household_matches is not None,
            "response_format": "json" if parsed_response else "text",
            "parsed_response_keys": sorted(parsed_response.keys()) if parsed_response else [],
        }

    return LLMReasoningResponse(
        id=interaction.id,
        event_id=interaction.event_id,
        created_at=interaction.created_at,
        raw_response=interaction.raw_response,
        parsed_response=parsed_response,
        think_block=think_block,
        enrichment_sources=enrichment_sources,
        truncation_info=truncation_info,
        household_matches=household_matches,
        debug_info=debug_info,
    )


@router.get(
    "/events/{event_id}/prompt",
    response_model=dict[str, Any],
    responses={
        404: {"description": "Event or LLM reasoning not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_llm_prompt_debug(
    event_id: int,
    db: AsyncSession = Depends(get_read_db),
) -> dict[str, Any]:
    """Get the full prompt data for debugging (debug mode endpoint).

    Returns the complete enrichment snapshot and context that was sent
    to the LLM for analysis. Use this for debugging prompt construction
    and understanding what data was available.

    Args:
        event_id: The event ID to fetch prompt data for
        db: Database session

    Returns:
        Dictionary containing full enrichment snapshot and context sources

    Raises:
        HTTPException: 404 if event or LLM reasoning not found
    """
    # Verify event exists and get the event's llm_prompt
    query = (
        select(Event)
        .options(joinedload(Event.llm_interaction))
        .where(Event.id == event_id)
        .where(Event.deleted_at.is_(None))
    )
    result = await db.execute(query)
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} not found",
        )

    interaction = event.llm_interaction

    if not interaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "event_id": event_id,
                "message": "No LLM interaction record found for this event",
            },
        )

    return {
        "event_id": event_id,
        "llm_prompt": event.llm_prompt,
        "enrichment_snapshot": interaction.enrichment_snapshot,
        "context_sources": interaction.context_sources,
        "truncation_log": interaction.truncation_log,
        "household_matches": interaction.household_matches,
        "validation_result": interaction.validation_result,
    }
