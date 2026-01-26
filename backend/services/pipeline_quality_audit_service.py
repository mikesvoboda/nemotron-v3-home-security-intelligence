"""AI Pipeline Audit Service.

Handles creation of audit records, self-evaluation via Nemotron,
and aggregation of statistics.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

import httpx
import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.core.json_utils import extract_json_from_llm_response, safe_json_loads
from backend.core.logging import get_logger
from backend.models.event import Event
from backend.models.event_audit import EventAudit

if TYPE_CHECKING:
    from backend.services.context_enricher import EnrichedContext
    from backend.services.enrichment_pipeline import EnrichmentResult

logger = get_logger(__name__)

# Model names for contribution tracking
MODEL_NAMES = [
    "yolo26",
    "florence",
    "clip",
    "violence",
    "clothing",
    "vehicle",
    "pet",
    "weather",
    "image_quality",
    "zones",
    "baseline",
    "cross_camera",
]

# Evaluation prompt templates
SELF_CRITIQUE_PROMPT = """<|im_start|>system
You are evaluating your own previous security analysis. Be critical and objective.<|im_end|>
<|im_start|>user
You previously analyzed a security event and provided this assessment:
- Risk Score: {risk_score}
- Summary: {summary}
- Reasoning: {reasoning}

Original context provided to you:
{llm_prompt}

Critique your own response:
1. What did you do well?
2. What could be improved?
3. What context did you ignore or underweight?

Provide a concise critique (2-3 paragraphs).<|im_end|>
<|im_start|>assistant
"""

RUBRIC_EVAL_PROMPT = """<|im_start|>system
You are scoring a security analysis on specific quality dimensions. Output valid JSON only.<|im_end|>
<|im_start|>user
Evaluate this security analysis on a 1-5 scale for each dimension:

Original prompt given: {llm_prompt}

Response produced:
- Risk Score: {risk_score}
- Summary: {summary}
- Reasoning: {reasoning}

Score each dimension (1=poor, 3=adequate, 5=excellent):
1. CONTEXT_USAGE: Did the analysis reference all relevant enrichment data provided?
2. REASONING_COHERENCE: Is the reasoning logical, well-structured, and easy to follow?
3. RISK_JUSTIFICATION: Does the evidence presented support the assigned risk score?
4. ACTIONABILITY: Is the summary useful and actionable for a homeowner?

Output JSON: {{"context_usage": N, "reasoning_coherence": N, "risk_justification": N, "actionability": N, "explanation": "brief explanation"}}<|im_end|>
<|im_start|>assistant
"""

CONSISTENCY_CHECK_PROMPT = """<|im_start|>system
You are a home security risk analyzer. Output valid JSON only.<|im_end|>
<|im_start|>user
{llm_prompt_clean}

Output JSON: {{"risk_score": N, "risk_level": "level", "brief_reason": "one sentence"}}<|im_end|>
<|im_start|>assistant
"""

PROMPT_IMPROVEMENT_PROMPT = """<|im_start|>system
You are analyzing a prompt template for improvement opportunities. Output valid JSON only.<|im_end|>
<|im_start|>user
You were given this prompt for security analysis:

{llm_prompt}

And you produced this response:
- Risk Score: {risk_score}
- Reasoning: {reasoning}

Analyze the PROMPT itself (not your response). What would help you make better assessments?

Identify:
1. MISSING_CONTEXT: What information would have helped? (e.g., "time since last motion", "historical activity")
2. CONFUSING_SECTIONS: Which parts were unclear or contradictory?
3. UNUSED_DATA: Which provided data was not useful for this analysis?
4. FORMAT_SUGGESTIONS: How could the prompt structure be improved?
5. MODEL_GAPS: Which AI models should have provided data but didn't?

Output JSON: {{
  "missing_context": ["item1", "item2"],
  "confusing_sections": ["item1"],
  "unused_data": ["item1"],
  "format_suggestions": ["item1"],
  "model_gaps": ["item1"]
}}<|im_end|>
<|im_start|>assistant
"""


class PipelineQualityAuditService:
    """Service for AI pipeline auditing and self-evaluation."""

    def __init__(self) -> None:
        # Lazy load settings to avoid module-level database URL requirement
        settings = get_settings()
        self._llm_url = settings.nemotron_url
        self._timeout = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)

    def create_partial_audit(
        self,
        event_id: int,
        llm_prompt: str | None,
        enriched_context: EnrichedContext | None,
        enrichment_result: EnrichmentResult | None,
    ) -> EventAudit:
        """Create a partial audit record with model contribution flags.

        Called inline when event is created. Does NOT call LLM.
        """
        audit = EventAudit(
            event_id=event_id,
            audited_at=datetime.now(UTC),
            # Model contributions
            has_yolo26=True,  # Always true if we have detections
            has_florence=self._has_florence(enrichment_result),
            has_clip=self._has_clip(enrichment_result),
            has_violence=self._has_violence(enrichment_result),
            has_clothing=self._has_clothing(enrichment_result),
            has_vehicle=self._has_vehicle(enrichment_result),
            has_pet=self._has_pet(enrichment_result),
            has_weather=self._has_weather(enrichment_result),
            has_image_quality=self._has_image_quality(enrichment_result),
            has_zones=self._has_zones(enriched_context),
            has_baseline=self._has_baseline(enriched_context),
            has_cross_camera=self._has_cross_camera(enriched_context),
            # Prompt metrics
            prompt_length=len(llm_prompt) if llm_prompt else 0,
            prompt_token_estimate=self._estimate_tokens(llm_prompt),
            enrichment_utilization=self._calc_utilization(enriched_context, enrichment_result),
        )
        return audit

    async def persist_record(
        self,
        audit: EventAudit,
        session: AsyncSession,
    ) -> EventAudit:
        """Persist an audit record to the database.

        Args:
            audit: The EventAudit record to persist.
            session: The database session to use for persistence.

        Returns:
            The persisted EventAudit with its ID populated.
        """
        session.add(audit)
        await session.commit()
        await session.refresh(audit)
        logger.debug(f"Persisted audit {audit.id} for event {audit.event_id}")
        return audit

    def _has_florence(self, result: EnrichmentResult | None) -> bool:
        return result is not None and result.has_vision_extraction

    def _has_clip(self, result: EnrichmentResult | None) -> bool:
        return result is not None and bool(
            result.person_reid_matches or result.vehicle_reid_matches
        )

    def _has_violence(self, result: EnrichmentResult | None) -> bool:
        return result is not None and result.has_violence

    def _has_clothing(self, result: EnrichmentResult | None) -> bool:
        return result is not None and result.has_clothing_classifications

    def _has_vehicle(self, result: EnrichmentResult | None) -> bool:
        return result is not None and (
            result.has_vehicle_classifications or result.has_vehicle_damage
        )

    def _has_pet(self, result: EnrichmentResult | None) -> bool:
        return result is not None and result.has_pet_classifications

    def _has_weather(self, result: EnrichmentResult | None) -> bool:
        return result is not None and result.weather_classification is not None

    def _has_image_quality(self, result: EnrichmentResult | None) -> bool:
        return result is not None and result.has_image_quality

    def _has_zones(self, context: EnrichedContext | None) -> bool:
        return context is not None and bool(context.zones)

    def _has_baseline(self, context: EnrichedContext | None) -> bool:
        return context is not None and context.baselines is not None

    def _has_cross_camera(self, context: EnrichedContext | None) -> bool:
        return context is not None and context.cross_camera is not None

    def _estimate_tokens(self, text: str | None) -> int:
        """Rough token estimate (chars / 4)."""
        if not text:
            return 0
        return len(text) // 4

    def _calc_utilization(
        self,
        context: EnrichedContext | None,
        result: EnrichmentResult | None,
    ) -> float:
        """Calculate enrichment utilization (0-1)."""
        total = 12  # Total possible enrichments
        count = sum(
            [
                True,  # yolo26 always
                self._has_florence(result),
                self._has_clip(result),
                self._has_violence(result),
                self._has_clothing(result),
                self._has_vehicle(result),
                self._has_pet(result),
                self._has_weather(result),
                self._has_image_quality(result),
                self._has_zones(context),
                self._has_baseline(context),
                self._has_cross_camera(context),
            ]
        )
        return count / total

    async def run_evaluation_llm_calls(
        self,
        audit: EventAudit,
        event: Event,
    ) -> EventAudit:
        """Run all 4 self-evaluation LLM calls and update audit in memory.

        This method performs only the LLM calls and updates the audit object
        attributes in memory. It does NOT perform any database operations.
        The caller is responsible for persisting the changes.

        This split allows the caller to manage database sessions properly,
        avoiding MissingGreenlet errors when LLM calls take a long time.

        Args:
            audit: The EventAudit record to update (can be detached from session).
            event: The Event to evaluate (can be detached from session).

        Returns:
            The updated EventAudit object (same object, modified in place).
        """
        if not event.llm_prompt:
            logger.warning(f"Event {event.id} has no llm_prompt, skipping evaluation")
            return audit

        # Mode 1: Self-critique
        critique = await self._run_self_critique(event)
        audit.self_eval_critique = critique

        # Mode 2: Rubric scoring
        scores = await self._run_rubric_eval(event)
        audit.context_usage_score = scores.get("context_usage")
        audit.reasoning_coherence_score = scores.get("reasoning_coherence")
        audit.risk_justification_score = scores.get("risk_justification")
        # Actionability maps to overall for now
        actionability = scores.get("actionability", 3.0)

        # Calculate overall as average of available scores
        score_values = [
            audit.context_usage_score,
            audit.reasoning_coherence_score,
            audit.risk_justification_score,
            actionability,
        ]
        valid_scores = [s for s in score_values if s is not None]
        audit.overall_quality_score = (
            sum(valid_scores) / len(valid_scores) if valid_scores else None
        )

        # Mode 3: Consistency check
        consistency_result = await self._run_consistency_check(event)
        audit.consistency_risk_score = consistency_result.get("risk_score")
        if audit.consistency_risk_score is not None and event.risk_score is not None:
            audit.consistency_diff = abs(audit.consistency_risk_score - event.risk_score)
            # Score consistency: 5 if diff <= 5, down to 1 if diff >= 25
            audit.consistency_score = max(1.0, 5.0 - (audit.consistency_diff / 5))

        # Mode 4: Prompt improvement
        improvements = await self._run_prompt_improvement(event)
        audit.missing_context = json.dumps(improvements.get("missing_context", []))
        audit.confusing_sections = json.dumps(improvements.get("confusing_sections", []))
        audit.unused_data = json.dumps(improvements.get("unused_data", []))
        audit.format_suggestions = json.dumps(improvements.get("format_suggestions", []))
        audit.model_gaps = json.dumps(improvements.get("model_gaps", []))

        # Store the evaluation prompt for debugging
        audit.self_eval_prompt = RUBRIC_EVAL_PROMPT.format(
            llm_prompt=event.llm_prompt[:500] + "..."
            if len(event.llm_prompt) > 500
            else event.llm_prompt,
            risk_score=event.risk_score,
            summary=event.summary,
            reasoning=event.reasoning[:300] + "..."
            if event.reasoning and len(event.reasoning) > 300
            else event.reasoning,
        )

        audit.audited_at = datetime.now(UTC)

        return audit

    async def run_full_evaluation(
        self,
        audit: EventAudit,
        event: Event,
        session: AsyncSession,
    ) -> EventAudit:
        """Run all 4 self-evaluation modes on an event.

        Updates the audit record with scores and recommendations.

        WARNING: This method makes 4 LLM calls (up to 120s each) while holding
        the session open. For background evaluation where sessions may be held
        for extended periods, use run_evaluation_llm_calls() instead and manage
        the session separately to avoid MissingGreenlet errors.

        Args:
            audit: The EventAudit record to update.
            event: The Event to evaluate.
            session: Database session for committing changes.

        Returns:
            The updated and refreshed EventAudit object.
        """
        # Early return if no llm_prompt (preserves original behavior)
        if not event.llm_prompt:
            logger.warning(f"Event {event.id} has no llm_prompt, skipping evaluation")
            return audit

        # Run LLM calls and update audit attributes
        await self.run_evaluation_llm_calls(audit, event)

        # Persist changes
        await session.commit()
        await session.refresh(audit)

        return audit

    async def _call_llm(self, prompt: str) -> str:
        """Call Nemotron LLM and return completion text."""
        payload = {
            "prompt": prompt,
            "temperature": 0.3,  # Lower temp for evaluation
            "top_p": 0.9,
            "max_tokens": 1024,
            "stop": ["<|im_end|>", "<|im_start|>"],
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._llm_url}/completion",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            result = response.json()

        content: str = result.get("content", "")
        return content

    async def _run_self_critique(self, event: Event) -> str:
        """Run Mode 1: Self-critique."""
        try:
            prompt = SELF_CRITIQUE_PROMPT.format(
                risk_score=event.risk_score,
                summary=event.summary,
                reasoning=event.reasoning,
                llm_prompt=event.llm_prompt,
            )
            return await self._call_llm(prompt)
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.error("Self-critique network error", exc_info=True, extra={"event_id": event.id})
            return f"Evaluation network error: {e}"
        except Exception as e:
            logger.error("Self-critique error", exc_info=True, extra={"event_id": event.id})
            return f"Evaluation error: {e}"

    async def _run_rubric_eval(self, event: Event) -> dict[str, float]:
        """Run Mode 2: Rubric scoring."""
        try:
            prompt = RUBRIC_EVAL_PROMPT.format(
                llm_prompt=event.llm_prompt,
                risk_score=event.risk_score,
                summary=event.summary,
                reasoning=event.reasoning,
            )
            response = await self._call_llm(prompt)

            # Parse JSON from response using robust extraction
            try:
                parsed: dict[str, float] = extract_json_from_llm_response(response)
                return parsed
            except ValueError:
                logger.warning(f"Could not extract JSON from rubric eval for event {event.id}")
                return {}
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError):
            logger.error("Rubric eval network error", exc_info=True, extra={"event_id": event.id})
            return {}
        except Exception:
            logger.error("Rubric eval error", exc_info=True, extra={"event_id": event.id})
            return {}

    async def _run_consistency_check(self, event: Event) -> dict[str, Any]:
        """Run Mode 3: Consistency check."""
        try:
            # Remove the assistant's previous response from prompt
            clean_prompt = event.llm_prompt or ""
            if "<|im_start|>assistant" in clean_prompt:
                clean_prompt = clean_prompt.split("<|im_start|>assistant")[0]

            prompt = CONSISTENCY_CHECK_PROMPT.format(llm_prompt_clean=clean_prompt)
            response = await self._call_llm(prompt)

            # Parse JSON from response using robust extraction
            try:
                parsed: dict[str, Any] = extract_json_from_llm_response(response)
                return parsed
            except ValueError:
                logger.warning(
                    f"Could not extract JSON from consistency check for event {event.id}"
                )
                return {}
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError):
            logger.error(
                "Consistency check network error", exc_info=True, extra={"event_id": event.id}
            )
            return {}
        except Exception:
            logger.error("Consistency check error", exc_info=True, extra={"event_id": event.id})
            return {}

    async def _run_prompt_improvement(self, event: Event) -> dict[str, list[str]]:
        """Run Mode 4: Prompt improvement suggestions."""
        try:
            prompt = PROMPT_IMPROVEMENT_PROMPT.format(
                llm_prompt=event.llm_prompt,
                risk_score=event.risk_score,
                reasoning=event.reasoning,
            )
            response = await self._call_llm(prompt)

            # Parse JSON from response using robust extraction
            try:
                parsed: dict[str, list[str]] = extract_json_from_llm_response(response)
                return parsed
            except ValueError:
                logger.warning(
                    f"Could not extract JSON from prompt improvement for event {event.id}"
                )
                return {}
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError):
            logger.error(
                "Prompt improvement network error", exc_info=True, extra={"event_id": event.id}
            )
            return {}
        except Exception:
            logger.error("Prompt improvement error", exc_info=True, extra={"event_id": event.id})
            return {}

    def _compute_daily_breakdown(
        self,
        audits: list[EventAudit],
    ) -> list[dict[str, Any]]:
        """Compute daily breakdown of audit statistics.

        Returns a list of dicts with:
        - date: ISO date string (YYYY-MM-DD)
        - day_of_week: Day name (Monday, Tuesday, etc.)
        - count: Number of audits on that day
        - avg_quality_score: Average quality score for that day (None if no scores)
        - avg_enrichment_utilization: Average enrichment utilization for that day
        - model_contributions: Dict of model name -> count for that day
        """
        if not audits:
            return []

        # Group audits by date
        daily_groups: dict[str, list[EventAudit]] = defaultdict(list)
        for audit in audits:
            if audit.audited_at:
                date_key = audit.audited_at.date().isoformat()
                daily_groups[date_key].append(audit)

        # Build daily breakdown
        daily_breakdown = []
        for date_str in sorted(daily_groups.keys()):
            day_audits = daily_groups[date_str]
            date_obj = datetime.fromisoformat(date_str).date()

            # Calculate averages for the day
            quality_scores = [
                a.overall_quality_score for a in day_audits if a.overall_quality_score is not None
            ]
            utilization_values = [a.enrichment_utilization for a in day_audits]

            # Count model contributions for the day
            model_contributions: dict[str, int] = {}
            for model in MODEL_NAMES:
                attr = f"has_{model}"
                model_contributions[model] = sum(1 for a in day_audits if getattr(a, attr, False))

            daily_breakdown.append(
                {
                    "date": date_str,
                    "day_of_week": date_obj.strftime("%A"),
                    "count": len(day_audits),
                    "avg_quality_score": (
                        sum(quality_scores) / len(quality_scores) if quality_scores else None
                    ),
                    "avg_enrichment_utilization": (
                        sum(utilization_values) / len(utilization_values)
                        if utilization_values
                        else None
                    ),
                    "model_contributions": model_contributions,
                }
            )

        return daily_breakdown

    def _compute_quality_correlations(
        self,
        audits: list[EventAudit],
    ) -> dict[str, float | None]:
        """Compute Pearson correlation between each model's presence and quality scores.

        For each model, calculates the correlation between:
        - A binary indicator (1 if model contributed, 0 if not)
        - The overall quality score

        Returns a dict mapping model name to correlation coefficient (-1.0 to 1.0).
        Returns None for a model if:
        - Not enough data points (need at least 3 with quality scores)
        - No variance in the model presence (all 1s or all 0s)
        - Correlation cannot be computed (e.g., constant values)
        """
        if not audits:
            return dict.fromkeys(MODEL_NAMES, None)

        # Filter to audits with quality scores
        audits_with_scores = [a for a in audits if a.overall_quality_score is not None]

        # Need at least 3 data points for meaningful correlation
        if len(audits_with_scores) < 3:
            return dict.fromkeys(MODEL_NAMES, None)

        # Extract quality scores as numpy array
        quality_scores = np.array(
            [a.overall_quality_score for a in audits_with_scores], dtype=np.float64
        )

        # Check if quality scores have variance
        if np.std(quality_scores) == 0:
            return dict.fromkeys(MODEL_NAMES, None)

        correlations: dict[str, float | None] = {}

        for model in MODEL_NAMES:
            attr = f"has_{model}"

            # Create binary indicator array for model presence
            model_presence = np.array(
                [1.0 if getattr(a, attr, False) else 0.0 for a in audits_with_scores],
                dtype=np.float64,
            )

            # Check if model presence has variance (not all 0s or all 1s)
            if np.std(model_presence) == 0:
                correlations[model] = None
                continue

            # Compute Pearson correlation coefficient
            # Using numpy's corrcoef which returns a 2x2 correlation matrix
            try:
                corr_matrix = np.corrcoef(model_presence, quality_scores)
                correlation = corr_matrix[0, 1]

                # Handle NaN result (can happen with edge cases)
                if np.isnan(correlation):
                    correlations[model] = None
                else:
                    # Round to 4 decimal places for cleaner output
                    correlations[model] = round(float(correlation), 4)
            except (ValueError, FloatingPointError):
                correlations[model] = None

        return correlations

    async def get_stats(
        self,
        session: AsyncSession,
        days: int = 7,
        camera_id: str | None = None,
    ) -> dict[str, Any]:
        """Get aggregate audit statistics.

        Returns dict with keys matching AuditStatsResponse schema:
        - total_events
        - audited_events
        - fully_evaluated_events
        - avg_quality_score
        - avg_consistency_rate
        - avg_enrichment_utilization
        - model_contribution_rates (dict of model -> rate 0-1)
        - audits_by_day
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)

        # Base query
        query = select(EventAudit).join(Event).where(EventAudit.audited_at >= cutoff)
        if camera_id:
            query = query.where(Event.camera_id == camera_id)

        result = await session.execute(query)
        audits = list(result.scalars().all())

        total_events = len(audits)
        fully_evaluated = sum(1 for a in audits if a.is_fully_evaluated)

        # Calculate averages
        quality_scores = [a.overall_quality_score for a in audits if a.overall_quality_score]
        consistency_scores = [a.consistency_score for a in audits if a.consistency_score]
        utilization_values = [a.enrichment_utilization for a in audits]

        # Model contribution rates (key name matches schema: model_contribution_rates)
        model_contribution_rates: dict[str, float] = {}
        for model in MODEL_NAMES:
            attr = f"has_{model}"
            count = sum(1 for a in audits if getattr(a, attr, False))
            model_contribution_rates[model] = count / total_events if total_events > 0 else 0

        # Calculate avg_consistency_rate (required by schema)
        avg_consistency_rate = (
            sum(consistency_scores) / len(consistency_scores) if consistency_scores else None
        )

        return {
            "total_events": total_events,
            "audited_events": total_events,
            "fully_evaluated_events": fully_evaluated,
            "avg_quality_score": sum(quality_scores) / len(quality_scores)
            if quality_scores
            else None,
            "avg_consistency_rate": avg_consistency_rate,
            "avg_enrichment_utilization": sum(utilization_values) / len(utilization_values)
            if utilization_values
            else None,
            "model_contribution_rates": model_contribution_rates,
            "audits_by_day": self._compute_daily_breakdown(audits),
        }

    async def get_leaderboard(
        self,
        session: AsyncSession,
        days: int = 7,
    ) -> list[dict[str, Any]]:
        """Get model leaderboard ranked by contribution rate.

        Returns list of dicts with keys matching ModelLeaderboardEntry schema:
        - model_name
        - contribution_rate
        - quality_correlation
        - event_count
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)

        # Fetch audits for correlation calculation
        result = await session.execute(select(EventAudit).where(EventAudit.audited_at >= cutoff))
        audits = list(result.scalars().all())

        stats = await self.get_stats(session, days)

        # Compute quality correlations for each model
        quality_correlations = self._compute_quality_correlations(audits)

        entries = []
        for model in MODEL_NAMES:
            rate = stats["model_contribution_rates"].get(model, 0)
            entries.append(
                {
                    "model_name": model,
                    "contribution_rate": rate,
                    "quality_correlation": quality_correlations.get(model),
                    "event_count": int(rate * stats["total_events"]),
                }
            )

        # Sort by contribution rate descending
        entries.sort(key=lambda x: x["contribution_rate"], reverse=True)
        return entries

    async def get_recommendations(
        self,
        session: AsyncSession,
        days: int = 7,
    ) -> list[dict[str, Any]]:
        """Aggregate recommendations from all audits."""
        cutoff = datetime.now(UTC) - timedelta(days=days)

        result = await session.execute(
            select(EventAudit).where(
                EventAudit.audited_at >= cutoff,
                EventAudit.overall_quality_score.isnot(None),
            )
        )
        audits = list(result.scalars().all())

        # Aggregate suggestions by category
        categories = ["missing_context", "unused_data", "model_gaps", "format_suggestions"]
        suggestions: dict[str, dict[str, int]] = {cat: {} for cat in categories}

        for audit in audits:
            for cat in categories:
                items_json = getattr(audit, cat, None)
                if items_json:
                    items = safe_json_loads(
                        items_json,
                        default=[],
                        context=f"EventAudit.{cat} (audit_id={audit.id})",
                    )
                    if isinstance(items, list):
                        for item in items:
                            suggestions[cat][item] = suggestions[cat].get(item, 0) + 1

        # Build recommendations list
        recommendations = []
        for cat, items in suggestions.items():
            for suggestion, count in sorted(items.items(), key=lambda x: -x[1])[:5]:
                recommendations.append(
                    {
                        "category": cat,
                        "suggestion": suggestion,
                        "frequency": count,
                        "priority": "high"
                        if count > len(audits) * 0.3
                        else "medium"
                        if count > len(audits) * 0.1
                        else "low",
                    }
                )

        recommendations.sort(key=lambda x: -cast("int", x["frequency"]))
        return recommendations[:20]


# Singleton
_audit_service: PipelineQualityAuditService | None = None


def get_audit_service() -> PipelineQualityAuditService:
    """Get or create audit service singleton."""
    global _audit_service  # noqa: PLW0603
    if _audit_service is None:
        _audit_service = PipelineQualityAuditService()
    return _audit_service


def reset_audit_service() -> None:
    """Reset the audit service singleton (for testing)."""
    global _audit_service  # noqa: PLW0603
    _audit_service = None
