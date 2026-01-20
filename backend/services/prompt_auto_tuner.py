"""Prompt Auto-Tuning Service.

This service uses accumulated audit feedback to improve LLM prompts by injecting
historical recommendations into the analysis prompt. It connects the self-evaluation
system (PipelineQualityAuditService) with the prompt generation pipeline.

The auto-tuner aggregates recommendations from past audits and formats them
as an additional context section that helps the LLM understand:
- What context was previously missing and helpful
- Known prompt clarity issues and how to address them

Usage:
    tuner = get_prompt_auto_tuner()
    auto_tune_context = await tuner.get_tuning_context(
        session=db_session,
        camera_id="front_door",
    )
    # Inject auto_tune_context into prompt template
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger
from backend.services.pipeline_quality_audit_service import (
    PipelineQualityAuditService,
    get_audit_service,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

# Priority levels for filtering recommendations
PRIORITY_LEVELS = {"high": 3, "medium": 2, "low": 1}


class PromptAutoTuner:
    """Use accumulated audit feedback to improve prompts.

    This service connects the self-evaluation recommendations from
    PipelineQualityAuditService with prompt generation by formatting
    historical insights into a context section for injection.

    Attributes:
        _audit_service: Service for fetching audit recommendations.
    """

    def __init__(
        self,
        audit_service: PipelineQualityAuditService | None = None,
    ) -> None:
        """Initialize the prompt auto-tuner.

        Args:
            audit_service: Optional custom audit service. If not provided,
                          uses the global singleton.
        """
        self._audit_service = audit_service

    def _get_audit_service(self) -> PipelineQualityAuditService:
        """Get the audit service, using global singleton if not set.

        Returns:
            PipelineQualityAuditService instance
        """
        if self._audit_service is None:
            self._audit_service = get_audit_service()
        return self._audit_service

    def _filter_by_priority(
        self,
        recommendations: list[dict[str, Any]],
        min_priority: str,
    ) -> list[dict[str, Any]]:
        """Filter recommendations by minimum priority level.

        Args:
            recommendations: List of recommendation dictionaries
            min_priority: Minimum priority level to include ('high', 'medium', 'low')

        Returns:
            Filtered list of recommendations at or above min_priority
        """
        min_level = PRIORITY_LEVELS.get(min_priority.lower(), 2)  # Default to medium
        return [
            r
            for r in recommendations
            if PRIORITY_LEVELS.get(r.get("priority", "low").lower(), 1) >= min_level
        ]

    async def get_tuning_context(
        self,
        session: AsyncSession,
        camera_id: str,
        days: int = 14,
        min_priority: str = "medium",
    ) -> str:
        """Get auto-tuning recommendations for prompt injection.

        Fetches recent recommendations from the audit service and formats
        them into a context section that can be injected into LLM prompts.

        Args:
            session: Database session for querying audits
            camera_id: Camera identifier for filtering recommendations
            days: Number of days to look back for recommendations (default: 14)
            min_priority: Minimum priority level to include ('high', 'medium', 'low')

        Returns:
            Formatted auto-tuning context string, or empty string if no
            recommendations are available or an error occurs.

        Example output:
            ## AUTO-TUNING (From Historical Analysis)
            Previously helpful context that was missing:
              - Include time since last motion event
              - Add historical activity patterns
            Known prompt clarity issues:
              - Structure detection list by object type
        """
        try:
            audit_service = self._get_audit_service()
            recommendations = await audit_service.get_recommendations(
                session=session,
                days=days,
            )

            if not recommendations:
                return ""

            # Filter by minimum priority
            recommendations = self._filter_by_priority(recommendations, min_priority)

            if not recommendations:
                return ""

            # Group by category
            missing_context = [
                r
                for r in recommendations
                if r.get("category") == "missing_context" and r.get("suggestion")
            ]
            format_suggestions = [
                r
                for r in recommendations
                if r.get("category") == "format_suggestions" and r.get("suggestion")
            ]

            # If no relevant categories, return empty
            if not missing_context and not format_suggestions:
                return ""

            lines = ["## AUTO-TUNING (From Historical Analysis)"]

            # Add missing context section (top 3)
            if missing_context:
                lines.append("Previously helpful context that was missing:")
                for r in missing_context[:3]:
                    suggestion = r.get("suggestion", "")
                    if suggestion:  # Skip empty suggestions
                        lines.append(f"  - {suggestion}")

            # Add format suggestions section (top 2)
            if format_suggestions:
                lines.append("Known prompt clarity issues:")
                for r in format_suggestions[:2]:
                    suggestion = r.get("suggestion", "")
                    if suggestion:  # Skip empty suggestions
                        lines.append(f"  - {suggestion}")

            return "\n".join(lines)

        except Exception as e:
            # Log error but don't fail the analysis pipeline
            logger.warning(
                "Failed to get auto-tuning context",
                extra={"camera_id": camera_id, "error": str(e)},
                exc_info=True,
            )
            return ""


# Singleton management
_prompt_auto_tuner: PromptAutoTuner | None = None


def get_prompt_auto_tuner() -> PromptAutoTuner:
    """Get or create the prompt auto-tuner singleton.

    Returns:
        PromptAutoTuner singleton instance
    """
    global _prompt_auto_tuner  # noqa: PLW0603
    if _prompt_auto_tuner is None:
        _prompt_auto_tuner = PromptAutoTuner()
    return _prompt_auto_tuner


def reset_prompt_auto_tuner() -> None:
    """Reset the prompt auto-tuner singleton (for testing)."""
    global _prompt_auto_tuner  # noqa: PLW0603
    _prompt_auto_tuner = None
