"""Prompt Management Service.

Handles CRUD operations for AI model prompt configurations,
version history, import/export, testing, A/B testing, shadow mode,
and performance comparison.
"""

from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import numpy as np
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.prompt_management import AIModelEnum
from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.models.prompt_version import PromptVersion
from backend.services.prompts import MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT

logger = get_logger(__name__)


# =============================================================================
# A/B Testing Configuration Classes (NEM-1667)
# =============================================================================


@dataclass
class ABTestConfig:
    """Configuration for A/B testing between prompt versions.

    Attributes:
        control_version: Version number of the control (current) prompt
        treatment_version: Version number of the treatment (new) prompt
        traffic_split: Fraction of traffic to route to treatment (0.0 to 1.0)
        enabled: Whether A/B testing is active
        model: AI model name (e.g., "nemotron")
    """

    control_version: int
    treatment_version: int
    traffic_split: float
    model: str
    enabled: bool = True

    def __post_init__(self) -> None:
        """Validate configuration values."""
        if not 0.0 <= self.traffic_split <= 1.0:
            raise ValueError(f"traffic_split must be between 0.0 and 1.0, got {self.traffic_split}")


@dataclass
class ShadowModeConfig:
    """Configuration for shadow mode prompt comparison.

    In shadow mode, both control and shadow prompts are executed,
    but only the control result is used. Shadow results are logged
    for comparison analysis.

    Attributes:
        enabled: Whether shadow mode is active
        control_version: Version number of the control prompt
        shadow_version: Version number of the shadow (test) prompt
        model: AI model name (e.g., "nemotron")
        log_comparisons: Whether to log comparison results
    """

    enabled: bool
    control_version: int
    shadow_version: int
    model: str
    log_comparisons: bool = True


@dataclass
class ShadowComparisonResult:
    """Result of a shadow mode comparison between two prompts.

    Attributes:
        control_result: Response from the control prompt
        shadow_result: Response from the shadow prompt (None if disabled/failed)
        risk_score_diff: Absolute difference in risk scores
        control_latency_ms: Latency of control prompt in milliseconds
        shadow_latency_ms: Latency of shadow prompt in milliseconds
        shadow_error: Error message if shadow prompt failed
    """

    control_result: dict[str, Any]
    shadow_result: dict[str, Any] | None = None
    risk_score_diff: float = 0.0
    control_latency_ms: float = 0.0
    shadow_latency_ms: float = 0.0
    shadow_error: str | None = None


@dataclass
class RollbackConfig:
    """Configuration for automatic rollback based on performance degradation.

    Attributes:
        enabled: Whether automatic rollback is enabled
        max_latency_increase_pct: Max allowed latency increase percentage
        max_score_variance: Max allowed risk score variance
        min_samples: Minimum samples required before triggering rollback
        evaluation_window_hours: Time window for evaluation in hours
    """

    enabled: bool = True
    max_latency_increase_pct: float = 50.0
    max_score_variance: float = 15.0
    min_samples: int = 100
    evaluation_window_hours: int = 1


@dataclass
class RollbackCheckResult:
    """Result of a rollback check.

    Attributes:
        should_rollback: Whether rollback should be triggered
        reason: Reason for rollback (or why not triggered)
    """

    should_rollback: bool
    reason: str | None = None


@dataclass
class RollbackExecutionResult:
    """Result of executing a rollback.

    Attributes:
        success: Whether rollback was successful
        previous_version: Version that was rolled back from
        new_version: Version that is now active
    """

    success: bool
    previous_version: int | None = None
    new_version: int | None = None


@dataclass
class EvaluationBatch:
    """A batch of historical events for prompt evaluation.

    Attributes:
        events: List of historical events to evaluate against
        created_at: When this batch was created
    """

    events: list[Any]
    created_at: datetime


@dataclass
class EvaluationResults:
    """Results from evaluating a prompt version against a batch.

    Attributes:
        total_events: Number of events evaluated
        average_score_diff: Average difference from original scores
        score_variance: Variance in score differences
        average_latency_ms: Average latency in milliseconds
        score_correlation: Correlation with original scores
    """

    total_events: int = 0
    average_score_diff: float | None = None
    score_variance: float | None = None
    average_latency_ms: float = 0.0
    score_correlation: float | None = None


@dataclass
class VersionComparisonResult:
    """Result of comparing two prompt versions.

    Attributes:
        version_a_results: Evaluation results for version A
        version_b_results: Evaluation results for version B
        recommended_version: The recommended version based on results
    """

    version_a_results: EvaluationResults
    version_b_results: EvaluationResults
    recommended_version: int


# =============================================================================
# A/B Testing Classes (NEM-1667)
# =============================================================================


class PromptABTester:
    """Manages A/B testing traffic splitting between prompt versions."""

    def __init__(self, config: ABTestConfig) -> None:
        """Initialize the A/B tester.

        Args:
            config: A/B test configuration
        """
        self._config = config
        self._logger = get_logger(__name__)

    def select_prompt_version(self) -> tuple[int, bool]:
        """Select which prompt version to use for a request.

        Returns:
            Tuple of (version_number, is_treatment)
        """
        if not self._config.enabled:
            return (self._config.control_version, False)

        # Random selection based on traffic split
        # Using secrets for better randomness (not cryptographic, just A/B testing)
        random_value = secrets.randbelow(1000) / 1000.0
        if random_value <= self._config.traffic_split:
            return (self._config.treatment_version, True)
        else:
            return (self._config.control_version, False)

    async def record_prompt_execution(
        self,
        version: int,
        latency_seconds: float,
        risk_score: int | float,  # noqa: ARG002 - Reserved for future variance tracking
    ) -> None:
        """Record metrics for a prompt execution.

        Args:
            version: Prompt version that was executed
            latency_seconds: Execution latency in seconds
            risk_score: Risk score returned by the prompt (for future variance tracking)
        """
        from backend.core.metrics import record_prompt_latency

        record_prompt_latency(f"v{version}", latency_seconds)


class PromptShadowRunner:
    """Executes shadow mode comparison between prompt versions."""

    def __init__(self, config: ShadowModeConfig) -> None:
        """Initialize the shadow runner.

        Args:
            config: Shadow mode configuration
        """
        self._config = config
        self._logger = get_logger(__name__)

    async def run_shadow_comparison(
        self,
        context: str,
    ) -> ShadowComparisonResult:
        """Run both control and shadow prompts and compare results.

        Args:
            context: Detection context to analyze

        Returns:
            Comparison result with both responses and metrics
        """
        from backend.core.metrics import record_shadow_comparison

        # Run control prompt
        control_start = time.monotonic()
        control_result = await self._run_single_prompt(self._config.control_version, context)
        control_latency = (time.monotonic() - control_start) * 1000

        result = ShadowComparisonResult(
            control_result=control_result,
            control_latency_ms=control_latency,
        )

        if not self._config.enabled:
            return result

        # Run shadow prompt
        try:
            shadow_start = time.monotonic()
            shadow_result = await self._run_single_prompt(self._config.shadow_version, context)
            shadow_latency = (time.monotonic() - shadow_start) * 1000

            result.shadow_result = shadow_result
            result.shadow_latency_ms = shadow_latency

            # Calculate risk score difference
            control_score = control_result.get("risk_score", 0)
            shadow_score = shadow_result.get("risk_score", 0)
            result.risk_score_diff = abs(control_score - shadow_score)

            # Record shadow comparison metric
            record_shadow_comparison(self._config.model)

            if self._config.log_comparisons:
                self._logger.info(
                    f"Shadow comparison: control={control_score}, "
                    f"shadow={shadow_score}, diff={result.risk_score_diff}"
                )

        except Exception as e:
            result.shadow_error = str(e)
            self._logger.warning(f"Shadow prompt failed: {e}")

        return result

    async def _run_single_prompt(
        self,
        version: int,
        context: str,
    ) -> dict[str, Any]:
        """Run a single prompt version. To be implemented by subclass or mocked.

        Args:
            version: Prompt version to run
            context: Detection context

        Returns:
            Prompt response as dict
        """
        # This method should be overridden or mocked in tests
        # In production, it would call the NemotronAnalyzer
        raise NotImplementedError("_run_single_prompt must be implemented")


class PromptRollbackChecker:
    """Checks for performance degradation and triggers rollbacks."""

    def __init__(self, config: RollbackConfig) -> None:
        """Initialize the rollback checker.

        Args:
            config: Rollback configuration
        """
        self._config = config
        self._logger = get_logger(__name__)

    async def check_rollback_needed(self, metrics: Any) -> RollbackCheckResult:
        """Check if rollback should be triggered based on metrics.

        Args:
            metrics: Performance metrics to evaluate

        Returns:
            Result indicating whether rollback is needed
        """
        if not self._config.enabled:
            return RollbackCheckResult(should_rollback=False, reason="Rollback disabled")

        # Check minimum samples
        if metrics.sample_count < self._config.min_samples:
            return RollbackCheckResult(
                should_rollback=False,
                reason=f"Insufficient samples ({metrics.sample_count}/{self._config.min_samples})",
            )

        # Check latency threshold
        if metrics.latency_increase_pct > self._config.max_latency_increase_pct:
            return RollbackCheckResult(
                should_rollback=True,
                reason=f"Latency increase {metrics.latency_increase_pct:.1f}% exceeds threshold",
            )

        # Check score variance threshold
        if metrics.score_variance > self._config.max_score_variance:
            return RollbackCheckResult(
                should_rollback=True,
                reason=f"Score variance {metrics.score_variance:.1f} exceeds threshold",
            )

        return RollbackCheckResult(should_rollback=False, reason=None)

    async def execute_rollback(
        self,
        session: AsyncSession,  # noqa: ARG002 - Reserved for persisting rollback state
        ab_config: Any,
        reason: str,
    ) -> RollbackExecutionResult:
        """Execute a rollback to the control version.

        Args:
            session: Database session
            ab_config: Current A/B test configuration
            reason: Reason for rollback

        Returns:
            Result of the rollback execution
        """
        from backend.core.metrics import record_prompt_rollback

        try:
            # Disable A/B test
            await self._disable_ab_test(ab_config)

            # Log the rollback
            self._log_rollback(
                ab_config.control_version,
                ab_config.treatment_version,
                reason,
            )

            # Record metric
            record_prompt_rollback(
                ab_config.model if hasattr(ab_config, "model") else "nemotron", "performance"
            )

            return RollbackExecutionResult(
                success=True,
                previous_version=ab_config.treatment_version,
                new_version=ab_config.control_version,
            )
        except Exception as e:
            self._logger.error(f"Rollback failed: {e}")
            return RollbackExecutionResult(success=False)

    async def _disable_ab_test(self, ab_config: Any) -> None:
        """Disable the A/B test.

        Args:
            ab_config: A/B test configuration to disable
        """
        ab_config.enabled = False

    def _log_rollback(
        self,
        control_version: int,
        treatment_version: int,
        reason: str,
    ) -> None:
        """Log rollback event.

        Args:
            control_version: Version being rolled back to
            treatment_version: Version being rolled back from
            reason: Reason for rollback
        """
        self._logger.warning(
            f"Rolling back from v{treatment_version} to v{control_version}: {reason}"
        )


class PromptEvaluator:
    """Evaluates prompt versions against historical events."""

    def __init__(self) -> None:
        """Initialize the evaluator."""
        self._logger = get_logger(__name__)

    async def create_evaluation_batch(
        self,
        session: AsyncSession,
        hours_back: int = 24,
        sample_size: int = 100,
    ) -> EvaluationBatch:
        """Create a batch of historical events for evaluation.

        Args:
            session: Database session
            hours_back: How many hours back to look for events
            sample_size: Maximum number of events to include

        Returns:
            Batch of events for evaluation
        """
        from backend.models.event import Event

        cutoff = datetime.now(UTC) - timedelta(hours=hours_back)

        result = await session.execute(
            select(Event)
            .where(Event.started_at >= cutoff)
            .order_by(Event.started_at.desc())
            .limit(sample_size)
        )
        events = list(result.scalars().all())

        return EvaluationBatch(
            events=events,
            created_at=datetime.now(UTC),
        )

    async def evaluate_prompt_version(
        self,
        session: AsyncSession,  # noqa: ARG002 - Reserved for loading prompt config
        prompt_version: int,
        batch: EvaluationBatch,
    ) -> EvaluationResults:
        """Evaluate a prompt version against a batch of events.

        Args:
            session: Database session
            prompt_version: Version to evaluate
            batch: Batch of events to evaluate against

        Returns:
            Evaluation results
        """
        if not batch.events:
            return EvaluationResults(total_events=0)

        score_diffs: list[float] = []
        latencies: list[float] = []

        for event in batch.events:
            try:
                start_time = time.monotonic()
                result = await self._run_prompt_for_event(prompt_version, event)
                latency_ms = (time.monotonic() - start_time) * 1000

                new_score = result.get("risk_score", 0)
                original_score = getattr(event, "risk_score", 0)
                score_diffs.append(abs(new_score - original_score))
                latencies.append(latency_ms)

            except Exception as e:
                self._logger.warning(f"Evaluation failed for event {event.id}: {e}")

        if not score_diffs:
            return EvaluationResults(total_events=0)

        arr = np.array(score_diffs)

        return EvaluationResults(
            total_events=len(score_diffs),
            average_score_diff=float(np.mean(arr)),
            score_variance=float(np.var(arr)),
            average_latency_ms=float(np.mean(latencies)) if latencies else 0.0,
            score_correlation=self._calculate_correlation(batch.events, score_diffs),
        )

    async def compare_prompt_versions(
        self,
        session: AsyncSession,
        version_a: int,
        version_b: int,
        batch: EvaluationBatch,
    ) -> VersionComparisonResult:
        """Compare two prompt versions on the same batch.

        Args:
            session: Database session
            version_a: First version to compare
            version_b: Second version to compare
            batch: Batch of events to evaluate against

        Returns:
            Comparison result with recommendation
        """
        results_a = await self.evaluate_prompt_version(session, version_a, batch)
        results_b = await self.evaluate_prompt_version(session, version_b, batch)

        # Recommend version with lower average diff and variance
        # Lower is better (closer to original assessments)
        score_a = (results_a.average_score_diff or 0) + (results_a.score_variance or 0)
        score_b = (results_b.average_score_diff or 0) + (results_b.score_variance or 0)

        recommended = version_a if score_a <= score_b else version_b

        return VersionComparisonResult(
            version_a_results=results_a,
            version_b_results=results_b,
            recommended_version=recommended,
        )

    async def _run_prompt_for_event(
        self,
        version: int,
        event: Any,
    ) -> dict[str, Any]:
        """Run a prompt version for a specific event.

        Args:
            version: Prompt version to run
            event: Event to analyze

        Returns:
            Prompt response as dict
        """
        # To be implemented - would use the event's context
        raise NotImplementedError("_run_prompt_for_event must be implemented")

    def _calculate_correlation(
        self,
        events: list[Any],
        score_diffs: list[float],
    ) -> float | None:
        """Calculate correlation between original and new scores.

        Args:
            events: List of events
            score_diffs: List of score differences

        Returns:
            Pearson correlation coefficient or None
        """
        if len(events) < 2:
            return None

        original_scores = [getattr(e, "risk_score", 0) for e in events[: len(score_diffs)]]
        if len(original_scores) != len(score_diffs):
            return None

        try:
            correlation = np.corrcoef(original_scores, score_diffs)[0, 1]
            return float(correlation) if not np.isnan(correlation) else None
        except Exception:
            return None


# Default configurations for each model
DEFAULT_CONFIGS: dict[str, dict[str, Any]] = {
    AIModelEnum.NEMOTRON.value: {
        "system_prompt": MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT,
        "version": 1,
    },
    AIModelEnum.FLORENCE2.value: {
        "queries": [
            "What is the person doing?",
            "What objects are they carrying?",
            "Describe the environment",
            "Is there anything unusual in this scene?",
        ],
    },
    AIModelEnum.YOLO_WORLD.value: {
        "classes": [
            "knife",
            "gun",
            "package",
            "crowbar",
            "spray paint",
            "Amazon box",
            "FedEx package",
            "suspicious bag",
        ],
        "confidence_threshold": 0.35,
    },
    AIModelEnum.XCLIP.value: {
        "action_classes": [
            "loitering",
            "running away",
            "fighting",
            "breaking in",
            "climbing fence",
            "hiding",
            "normal walking",
        ],
    },
    AIModelEnum.FASHION_CLIP.value: {
        "clothing_categories": [
            "dark hoodie",
            "face mask",
            "gloves",
            "all black",
            "delivery uniform",
            "high-vis vest",
            "business attire",
        ],
    },
}


class PromptService:
    """Service for managing AI model prompt configurations."""

    def __init__(self) -> None:
        """Initialize the prompt service."""
        settings = get_settings()
        self._llm_url = settings.nemotron_url
        self._timeout = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)

    async def get_all_prompts(
        self,
        session: AsyncSession,
    ) -> dict[str, dict[str, Any]]:
        """Get current active prompt configurations for all models.

        Args:
            session: Database session

        Returns:
            Dict mapping model names to their active configurations
        """
        prompts: dict[str, dict[str, Any]] = {}

        for model_enum in AIModelEnum:
            model_name = model_enum.value
            config = await self.get_prompt_for_model(session, model_name)
            prompts[model_name] = config

        return prompts

    async def get_prompt_for_model(
        self,
        session: AsyncSession,
        model: str,
    ) -> dict[str, Any]:
        """Get the active prompt configuration for a specific model.

        Args:
            session: Database session
            model: Model name (e.g., 'nemotron', 'florence2')

        Returns:
            Configuration dict for the model
        """
        # Query for active version
        result = await session.execute(
            select(PromptVersion)
            .where(
                and_(
                    PromptVersion.model == model,
                    PromptVersion.is_active == True,  # noqa: E712
                )
            )
            .order_by(PromptVersion.version.desc())
            .limit(1)
        )
        version = result.scalar_one_or_none()

        if version:
            config = version.config.copy()
            config["version"] = version.version
            return config

        # Return default config if no version exists
        return DEFAULT_CONFIGS.get(model, {}).copy()

    async def update_prompt_for_model(
        self,
        session: AsyncSession,
        model: str,
        config: dict[str, Any],
        change_description: str | None = None,
        created_by: str | None = None,
        expected_version: int | None = None,
    ) -> PromptVersion:
        """Update prompt configuration for a model, creating a new version.

        Args:
            session: Database session
            model: Model name
            config: New configuration
            change_description: Optional description of changes
            created_by: Optional user identifier
            expected_version: If provided, used for optimistic locking. The update
                will fail if the current version doesn't match.

        Returns:
            The new PromptVersion record

        Raises:
            PromptVersionConflictError: If expected_version is provided and doesn't
                match the current version (concurrent modification detected)
        """
        from backend.api.schemas.prompt_management import PromptVersionConflictError

        # Get current max version for this model
        result = await session.execute(
            select(func.max(PromptVersion.version)).where(PromptVersion.model == model)
        )
        max_version = result.scalar() or 0
        new_version = max_version + 1

        # Optimistic locking check: verify expected_version matches current version
        if expected_version is not None and max_version > 0 and expected_version != max_version:
            logger.warning(
                f"Concurrent modification detected for model {model}: "
                f"expected version {expected_version}, actual version {max_version}",
                extra={
                    "model": model,
                    "expected_version": expected_version,
                    "actual_version": max_version,
                },
            )
            raise PromptVersionConflictError(
                model=model,
                expected_version=expected_version,
                actual_version=max_version,
            )

        # Deactivate all existing versions for this model
        await session.execute(
            update(PromptVersion).where(PromptVersion.model == model).values(is_active=False)
        )

        # Create new version
        new_prompt = PromptVersion(
            model=model,
            version=new_version,
            config_json=json.dumps(config),
            change_description=change_description,
            created_by=created_by,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        session.add(new_prompt)
        await session.commit()
        await session.refresh(new_prompt)

        logger.info(
            f"Created new prompt version {new_version} for model {model}",
            extra={"model": model, "version": new_version},
        )

        return new_prompt

    async def test_prompt(
        self,
        session: AsyncSession,
        model: str,
        config: dict[str, Any],
        event_id: int | None = None,
        image_path: str | None = None,
    ) -> dict[str, Any]:
        """Test a prompt configuration against an event or image.

        Args:
            session: Database session
            model: Model name to test
            config: Configuration to test
            event_id: Optional event ID to test against
            image_path: Optional image path to test with

        Returns:
            Test results including before/after comparison
        """
        start_time = time.monotonic()
        result: dict[str, Any] = {
            "model": model,
            "before_score": None,
            "after_score": None,
            "before_response": None,
            "after_response": None,
            "improved": None,
            "test_duration_ms": 0,
            "error": None,
        }

        try:
            # For now, only support Nemotron testing
            if model != AIModelEnum.NEMOTRON.value:
                result["error"] = f"Testing for model '{model}' not yet implemented"
                result["test_duration_ms"] = int((time.monotonic() - start_time) * 1000)
                return result

            if not event_id and not image_path:
                result["error"] = "Either event_id or image_path must be provided"
                result["test_duration_ms"] = int((time.monotonic() - start_time) * 1000)
                return result

            # Get the event if provided
            if event_id:
                from backend.models.event import Event

                event_result = await session.execute(select(Event).where(Event.id == event_id))
                event = event_result.scalar_one_or_none()

                if not event:
                    result["error"] = f"Event {event_id} not found"
                    result["test_duration_ms"] = int((time.monotonic() - start_time) * 1000)
                    return result

                # Store original score
                result["before_score"] = event.risk_score

                # Get the new prompt from config
                new_prompt = config.get("system_prompt", "")
                if not new_prompt:
                    result["error"] = "system_prompt not found in config"
                    result["test_duration_ms"] = int((time.monotonic() - start_time) * 1000)
                    return result

                # Test with new prompt
                test_response = await self._run_llm_test(new_prompt, event.llm_prompt)
                result["after_response"] = test_response
                result["after_score"] = test_response.get("risk_score")

                if result["before_score"] is not None and result["after_score"] is not None:
                    # Lower score is generally better (less false positives)
                    # But this depends on context - for now just show the difference
                    result["improved"] = abs(result["after_score"] - result["before_score"]) <= 10

        except httpx.TimeoutException as e:
            logger.warning(f"Prompt test timed out for model {model}: {e}")
            result["error"] = f"Request timed out: {e}"
        except httpx.HTTPStatusError as e:
            logger.warning(f"Prompt test HTTP error for model {model}: {e}")
            result["error"] = f"HTTP error: {e}"
        except httpx.RequestError as e:
            logger.warning(f"Prompt test request failed for model {model}: {e}")
            result["error"] = f"Request failed: {e}"
        except (KeyError, TypeError, ValueError) as e:
            logger.warning(f"Prompt test data error for model {model}: {e}")
            result["error"] = f"Data error: {e}"

        result["test_duration_ms"] = int((time.monotonic() - start_time) * 1000)
        return result

    async def _run_llm_test(
        self,
        system_prompt: str,
        context: str | None,
    ) -> dict[str, Any]:
        """Run LLM test with the given prompt.

        Args:
            system_prompt: The system prompt to test
            context: The context/user message

        Returns:
            LLM response as dict
        """
        if not context:
            return {"error": "No context available for testing"}

        payload = {
            "prompt": system_prompt + context,
            "temperature": 0.3,
            "top_p": 0.9,
            "max_tokens": 1024,
            "stop": ["<|im_end|>", "<|im_start|>"],
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._llm_url}/completion",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                result = response.json()

            content: str = result.get("content", "")

            # Try to parse JSON from response
            from backend.core.json_utils import extract_json_from_llm_response

            try:
                return extract_json_from_llm_response(content)
            except ValueError:
                return {"raw_response": content}
        except httpx.TimeoutException as e:
            return {"error": f"Request timed out: {e}"}
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP error {e.response.status_code}: {e}"}
        except httpx.RequestError as e:
            return {"error": f"Request failed: {e}"}

    async def get_version_history(
        self,
        session: AsyncSession,
        model: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PromptVersion], int]:
        """Get version history for prompts.

        Args:
            session: Database session
            model: Optional model to filter by
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            Tuple of (list of versions, total count)
        """
        # Build base query
        query = select(PromptVersion)
        count_query = select(func.count(PromptVersion.id))

        if model:
            query = query.where(PromptVersion.model == model)
            count_query = count_query.where(PromptVersion.model == model)

        # Get total count
        count_result = await session.execute(count_query)
        total_count = count_result.scalar() or 0

        # Get paginated results
        query = query.order_by(PromptVersion.created_at.desc()).offset(offset).limit(limit)

        result = await session.execute(query)
        versions = list(result.scalars().all())

        return versions, total_count

    async def restore_version(
        self,
        session: AsyncSession,
        version_id: int,
    ) -> PromptVersion:
        """Restore a specific version by creating a new version with the same config.

        Args:
            session: Database session
            version_id: ID of the version to restore

        Returns:
            The new active PromptVersion

        Raises:
            ValueError: If version not found
        """
        # Get the version to restore
        result = await session.execute(select(PromptVersion).where(PromptVersion.id == version_id))
        old_version = result.scalar_one_or_none()

        if not old_version:
            raise ValueError(f"Version {version_id} not found")

        # Create a new version with the same config
        return await self.update_prompt_for_model(
            session=session,
            model=old_version.model,
            config=old_version.config,
            change_description=f"Restored from version {old_version.version}",
        )

    async def export_all_prompts(
        self,
        session: AsyncSession,
    ) -> dict[str, Any]:
        """Export all prompt configurations.

        Args:
            session: Database session

        Returns:
            Export data structure
        """
        prompts = await self.get_all_prompts(session)

        return {
            "version": "1.0",
            "exported_at": datetime.now(UTC).isoformat(),
            "prompts": prompts,
        }

    async def import_prompts(
        self,
        session: AsyncSession,
        import_data: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Import prompt configurations.

        Args:
            session: Database session
            import_data: Prompts data to import

        Returns:
            Import result with counts and new versions
        """
        imported_models: list[str] = []
        skipped_models: list[str] = []
        new_versions: dict[str, int] = {}

        valid_models = {m.value for m in AIModelEnum}

        for model_name, config in import_data.items():
            if model_name not in valid_models:
                skipped_models.append(model_name)
                logger.warning(f"Skipping unknown model: {model_name}")
                continue

            try:
                new_version = await self.update_prompt_for_model(
                    session=session,
                    model=model_name,
                    config=config,
                    change_description="Imported from JSON",
                )
                imported_models.append(model_name)
                new_versions[model_name] = new_version.version
            except Exception as e:
                logger.error(f"Failed to import config for {model_name}: {e}")
                skipped_models.append(model_name)

        return {
            "imported_models": imported_models,
            "skipped_models": skipped_models,
            "new_versions": new_versions,
            "message": f"Imported {len(imported_models)} model configurations",
        }


# Singleton instance
_prompt_service: PromptService | None = None


def get_prompt_service() -> PromptService:
    """Get or create the prompt service singleton."""
    global _prompt_service  # noqa: PLW0603
    if _prompt_service is None:
        _prompt_service = PromptService()
    return _prompt_service


def reset_prompt_service() -> None:
    """Reset the prompt service singleton (for testing)."""
    global _prompt_service  # noqa: PLW0603
    _prompt_service = None
