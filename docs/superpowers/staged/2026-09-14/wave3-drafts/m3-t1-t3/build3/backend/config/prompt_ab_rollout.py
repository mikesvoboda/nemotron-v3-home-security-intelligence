"""Prompt A/B Rollout Configuration for Phase 7.2 (NEM-3338).

This module provides configuration and management for A/B testing new prompt
versions with automatic rollback capability. The key features are:

1. **50/50 Traffic Split**: Half of cameras use the old prompt (control),
   half use the new calibrated prompt (treatment).

2. **48-Hour Test Duration**: The experiment runs for 48 hours to collect
   sufficient statistical data.

3. **Auto-Rollback**: Automatically reverts to control if:
   - FP rate increases beyond threshold (default: +5%)
   - Latency increases beyond threshold (default: +50%)
   - Error rate increases beyond threshold (default: +5%)

4. **Metrics Collection**: Tracks per-group:
   - False positive rate via user feedback
   - Risk score distributions
   - Latency statistics
   - Error rates

Usage:
    from backend.config.prompt_ab_rollout import (
        ABRolloutConfig,
        AutoRollbackConfig,
        ABRolloutManager,
    )

    # Create configuration
    rollout_config = ABRolloutConfig(
        treatment_percentage=0.5,
        test_duration_hours=48,
    )
    rollback_config = AutoRollbackConfig(
        max_fp_rate_increase=0.05,
        max_latency_increase_pct=50.0,
    )

    # Start experiment
    manager = ABRolloutManager(rollout_config, rollback_config)
    manager.start()

    # During analysis
    group = manager.get_group_for_camera(camera_id)
    if group == ExperimentGroup.TREATMENT:
        # Use new prompt
        ...
        manager.record_treatment_analysis(latency_ms=150.0, risk_score=45)
    else:
        # Use old prompt
        ...
        manager.record_control_analysis(latency_ms=100.0, risk_score=50)

    # Check for rollback
    result = manager.check_rollback_needed()
    if result.should_rollback:
        manager.stop()
        # Revert to control
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from backend.core.logging import get_logger

logger = get_logger(__name__)


class ExperimentGroup(Enum):
    """Enumeration of experiment groups.

    Attributes:
        CONTROL: Uses the current production prompt (V1)
        TREATMENT: Uses the new calibrated prompt (V2)
    """

    CONTROL = "control"
    TREATMENT = "treatment"


@dataclass
class ABRolloutConfig:
    """Configuration for A/B testing prompt rollout.

    Attributes:
        treatment_percentage: Fraction of cameras to assign to treatment (0.0 to 1.0).
            Default is 0.5 for 50/50 split.
        test_duration_hours: Duration of the test in hours. Default is 48.
        experiment_name: Name of the experiment for tracking/logging.
        started_at: UTC timestamp when experiment started, or None if not started.

    Example:
        # Standard 50/50 split for 48 hours
        config = ABRolloutConfig()

        # Custom 30% treatment for 72 hours
        config = ABRolloutConfig(
            treatment_percentage=0.3,
            test_duration_hours=72,
        )
    """

    treatment_percentage: float = 0.5
    test_duration_hours: int = 48
    experiment_name: str = "nemotron_prompt_v2_rollout"
    started_at: datetime | None = None

    def __post_init__(self) -> None:
        """Validate configuration values after initialization."""
        if not 0.0 <= self.treatment_percentage <= 1.0:
            raise ValueError(
                f"treatment_percentage must be between 0.0 and 1.0, got {self.treatment_percentage}"
            )
        if self.test_duration_hours <= 0:
            raise ValueError(
                f"test_duration_hours must be positive, got {self.test_duration_hours}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize config to dictionary.

        Returns:
            Dictionary representation of the config
        """
        return {
            "treatment_percentage": self.treatment_percentage,
            "test_duration_hours": self.test_duration_hours,
            "experiment_name": self.experiment_name,
            "started_at": self.started_at.isoformat() if self.started_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ABRolloutConfig:
        """Create config from dictionary.

        Args:
            data: Dictionary with config fields

        Returns:
            ABRolloutConfig instance
        """
        started_at = None
        if data.get("started_at"):
            started_at = datetime.fromisoformat(data["started_at"])

        return cls(
            treatment_percentage=data.get("treatment_percentage", 0.5),
            test_duration_hours=data.get("test_duration_hours", 48),
            experiment_name=data.get("experiment_name", "nemotron_prompt_v2_rollout"),
            started_at=started_at,
        )


@dataclass
class AutoRollbackConfig:
    """Configuration for automatic rollback based on performance degradation.

    Auto-rollback triggers when the treatment group performs significantly worse
    than the control group in any of these metrics:
    - False positive rate
    - Latency
    - Error rate

    Attributes:
        max_fp_rate_increase: Maximum allowed FP rate increase (treatment - control).
            Default is 0.05 (5 percentage points).
        max_latency_increase_pct: Maximum allowed latency increase percentage.
            Default is 50.0%.
        max_error_rate_increase: Maximum allowed error rate increase.
            Default is 0.05 (5 percentage points).
        min_samples: Minimum samples in each group before triggering rollback.
            Default is 100.
        enabled: Whether automatic rollback is enabled. Default is True.

    Example:
        # Default configuration
        config = AutoRollbackConfig()

        # More lenient thresholds
        config = AutoRollbackConfig(
            max_fp_rate_increase=0.10,  # Allow 10% increase
            max_latency_increase_pct=100.0,  # Allow 100% increase
        )
    """

    max_fp_rate_increase: float = 0.05
    max_latency_increase_pct: float = 50.0
    max_error_rate_increase: float = 0.05
    min_samples: int = 100
    enabled: bool = True

    def __post_init__(self) -> None:
        """Validate configuration values after initialization."""
        if self.min_samples < 0:
            raise ValueError(f"min_samples must be non-negative, got {self.min_samples}")

    def to_dict(self) -> dict[str, Any]:
        """Serialize config to dictionary.

        Returns:
            Dictionary representation of the config
        """
        return {
            "max_fp_rate_increase": self.max_fp_rate_increase,
            "max_latency_increase_pct": self.max_latency_increase_pct,
            "max_error_rate_increase": self.max_error_rate_increase,
            "min_samples": self.min_samples,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AutoRollbackConfig:
        """Create config from dictionary.

        Args:
            data: Dictionary with config fields

        Returns:
            AutoRollbackConfig instance
        """
        return cls(
            max_fp_rate_increase=data.get("max_fp_rate_increase", 0.05),
            max_latency_increase_pct=data.get("max_latency_increase_pct", 50.0),
            max_error_rate_increase=data.get("max_error_rate_increase", 0.05),
            min_samples=data.get("min_samples", 100),
            enabled=data.get("enabled", True),
        )


@dataclass
class RollbackCheckResult:
    """Result of a rollback check.

    Attributes:
        should_rollback: Whether rollback should be triggered
        reason: Human-readable reason for the decision
    """

    should_rollback: bool
    reason: str


@dataclass
class GroupMetrics:
    """Metrics tracking for an experiment group.

    Tracks false positive rate, risk score distribution, latency,
    and error rate for a single group (control or treatment).

    Attributes:
        false_positive_count: Number of false positive feedbacks
        total_feedback_count: Total number of feedback submissions
        risk_scores: List of recorded risk scores
        latencies_ms: List of recorded latencies in milliseconds
        error_count: Number of analysis errors
        total_analyses: Total number of analyses attempted
    """

    false_positive_count: int = 0
    total_feedback_count: int = 0
    risk_scores: list[int] = field(default_factory=list)
    latencies_ms: list[float] = field(default_factory=list)
    error_count: int = 0
    total_analyses: int = 0

    @property
    def fp_rate(self) -> float:
        """Calculate false positive rate.

        Returns:
            FP rate as a fraction (0.0 to 1.0), or 0.0 if no feedback
        """
        if self.total_feedback_count == 0:
            return 0.0
        return self.false_positive_count / self.total_feedback_count

    @property
    def error_rate(self) -> float:
        """Calculate error rate.

        Returns:
            Error rate as a fraction (0.0 to 1.0), or 0.0 if no analyses
        """
        if self.total_analyses == 0:
            return 0.0
        return self.error_count / self.total_analyses

    @property
    def avg_risk_score(self) -> float | None:
        """Calculate average risk score.

        Returns:
            Average score, or None if no scores recorded
        """
        if not self.risk_scores:
            return None
        return sum(self.risk_scores) / len(self.risk_scores)

    @property
    def min_risk_score(self) -> int | None:
        """Get minimum risk score.

        Returns:
            Minimum score, or None if no scores recorded
        """
        if not self.risk_scores:
            return None
        return min(self.risk_scores)

    @property
    def max_risk_score(self) -> int | None:
        """Get maximum risk score.

        Returns:
            Maximum score, or None if no scores recorded
        """
        if not self.risk_scores:
            return None
        return max(self.risk_scores)

    @property
    def avg_latency_ms(self) -> float | None:
        """Calculate average latency in milliseconds.

        Returns:
            Average latency, or None if no latencies recorded
        """
        if not self.latencies_ms:
            return None
        return sum(self.latencies_ms) / len(self.latencies_ms)

    @property
    def latency_count(self) -> int:
        """Get count of latency samples.

        Returns:
            Number of latency samples recorded
        """
        return len(self.latencies_ms)

    def record_feedback(self, is_false_positive: bool) -> None:
        """Record a feedback submission.

        Args:
            is_false_positive: Whether the feedback indicates a false positive
        """
        self.total_feedback_count += 1
        if is_false_positive:
            self.false_positive_count += 1

    def record_risk_score(self, score: int) -> None:
        """Record a risk score from analysis.

        Args:
            score: Risk score (0-100)
        """
        self.risk_scores.append(score)
        self.total_analyses += 1

    def record_latency(self, latency_ms: float) -> None:
        """Record analysis latency.

        Args:
            latency_ms: Latency in milliseconds
        """
        self.latencies_ms.append(latency_ms)

    def record_analysis(
        self,
        has_error: bool = False,
        latency_ms: float | None = None,
        risk_score: int | None = None,
    ) -> None:
        """Record an analysis attempt.

        Args:
            has_error: Whether the analysis resulted in an error
            latency_ms: Optional latency in milliseconds
            risk_score: Optional risk score from the analysis
        """
        self.total_analyses += 1
        if has_error:
            self.error_count += 1
        if latency_ms is not None:
            self.latencies_ms.append(latency_ms)
        if risk_score is not None:
            self.risk_scores.append(risk_score)


class ABRolloutManager:
    """Manager for orchestrating A/B testing of prompt versions.

    Handles:
    - Camera-to-group assignment (consistent hash-based)
    - Metrics collection for both groups
    - Rollback condition checking
    - Experiment lifecycle (start/stop)

    Attributes:
        rollout_config: A/B test configuration
        rollback_config: Auto-rollback configuration
        control_metrics: Metrics for control group
        treatment_metrics: Metrics for treatment group
    """

    def __init__(
        self,
        rollout_config: ABRolloutConfig,
        rollback_config: AutoRollbackConfig,
    ) -> None:
        """Initialize the rollout manager.

        Args:
            rollout_config: A/B test configuration
            rollback_config: Auto-rollback configuration
        """
        self.rollout_config = rollout_config
        self.rollback_config = rollback_config
        self.control_metrics = GroupMetrics()
        self.treatment_metrics = GroupMetrics()
        self._is_active = False

    @property
    def is_active(self) -> bool:
        """Check if the experiment is currently active.

        Returns:
            True if experiment is running
        """
        return self._is_active

    @property
    def is_expired(self) -> bool:
        """Check if the experiment has exceeded its duration.

        Returns:
            True if experiment started and duration has elapsed
        """
        if self.rollout_config.started_at is None:
            return False

        elapsed = datetime.now(UTC) - self.rollout_config.started_at
        duration = timedelta(hours=self.rollout_config.test_duration_hours)
        return elapsed > duration

    @property
    def remaining_hours(self) -> float:
        """Calculate remaining hours in the experiment.

        Returns:
            Remaining hours, or 0 if expired/not started
        """
        if self.rollout_config.started_at is None:
            return self.rollout_config.test_duration_hours

        elapsed = datetime.now(UTC) - self.rollout_config.started_at
        duration = timedelta(hours=self.rollout_config.test_duration_hours)
        remaining = duration - elapsed

        return max(0, remaining.total_seconds() / 3600)

    def start(self) -> None:
        """Start the A/B experiment."""
        self.rollout_config.started_at = datetime.now(UTC)
        self._is_active = True
        logger.info(
            f"Started A/B experiment '{self.rollout_config.experiment_name}' "
            f"with {self.rollout_config.treatment_percentage:.0%} treatment split "
            f"for {self.rollout_config.test_duration_hours} hours"
        )

    def stop(self) -> None:
        """Stop the A/B experiment."""
        self._is_active = False
        logger.info(f"Stopped A/B experiment '{self.rollout_config.experiment_name}'")

    def get_group_for_camera(self, camera_id: str) -> ExperimentGroup:
        """Determine which experiment group a camera belongs to.

        Uses hash-based assignment for consistency - the same camera_id
        always maps to the same group.

        Args:
            camera_id: Camera identifier

        Returns:
            ExperimentGroup.CONTROL or ExperimentGroup.TREATMENT
        """
        # Hash-based assignment for consistency
        hash_val = hash(camera_id) % 100
        if hash_val < self.rollout_config.treatment_percentage * 100:
            return ExperimentGroup.TREATMENT
        return ExperimentGroup.CONTROL

    def record_control_feedback(self, is_false_positive: bool) -> None:
        """Record feedback for the control group.

        Args:
            is_false_positive: Whether the feedback indicates a false positive
        """
        self.control_metrics.record_feedback(is_false_positive)

    def record_treatment_feedback(self, is_false_positive: bool) -> None:
        """Record feedback for the treatment group.

        Args:
            is_false_positive: Whether the feedback indicates a false positive
        """
        self.treatment_metrics.record_feedback(is_false_positive)

    def record_control_analysis(
        self,
        latency_ms: float | None = None,
        risk_score: int | None = None,
        has_error: bool = False,
    ) -> None:
        """Record analysis metrics for the control group.

        Args:
            latency_ms: Optional latency in milliseconds
            risk_score: Optional risk score
            has_error: Whether the analysis resulted in an error
        """
        self.control_metrics.record_analysis(
            has_error=has_error,
            latency_ms=latency_ms,
            risk_score=risk_score,
        )

    def record_treatment_analysis(
        self,
        latency_ms: float | None = None,
        risk_score: int | None = None,
        has_error: bool = False,
    ) -> None:
        """Record analysis metrics for the treatment group.

        Args:
            latency_ms: Optional latency in milliseconds
            risk_score: Optional risk score
            has_error: Whether the analysis resulted in an error
        """
        self.treatment_metrics.record_analysis(
            has_error=has_error,
            latency_ms=latency_ms,
            risk_score=risk_score,
        )

    def check_rollback_needed(self) -> RollbackCheckResult:
        """Check if auto-rollback should be triggered.

        Evaluates:
        1. Whether auto-rollback is enabled
        2. Whether sufficient samples have been collected
        3. Whether treatment FP rate exceeds control + threshold
        4. Whether treatment latency exceeds control + threshold
        5. Whether treatment error rate exceeds control + threshold

        Returns:
            RollbackCheckResult with decision and reason
        """
        if not self.rollback_config.enabled:
            return RollbackCheckResult(should_rollback=False, reason="Auto-rollback is disabled")

        # Check minimum samples
        control_samples = self.control_metrics.total_feedback_count
        treatment_samples = self.treatment_metrics.total_feedback_count
        min_samples = self.rollback_config.min_samples

        if control_samples < min_samples or treatment_samples < min_samples:
            return RollbackCheckResult(
                should_rollback=False,
                reason=f"Insufficient samples: control={control_samples}, "
                f"treatment={treatment_samples}, required={min_samples}",
            )

        # Check FP rate increase
        control_fp_rate = self.control_metrics.fp_rate
        treatment_fp_rate = self.treatment_metrics.fp_rate
        fp_rate_increase = treatment_fp_rate - control_fp_rate

        if fp_rate_increase > self.rollback_config.max_fp_rate_increase:
            return RollbackCheckResult(
                should_rollback=True,
                reason=f"FP rate increase {fp_rate_increase:.1%} exceeds threshold "
                f"{self.rollback_config.max_fp_rate_increase:.1%} "
                f"(control={control_fp_rate:.1%}, treatment={treatment_fp_rate:.1%})",
            )

        # Check latency increase
        control_latency = self.control_metrics.avg_latency_ms
        treatment_latency = self.treatment_metrics.avg_latency_ms

        if control_latency and treatment_latency and control_latency > 0:
            latency_increase_pct = (treatment_latency - control_latency) / control_latency * 100
            if latency_increase_pct > self.rollback_config.max_latency_increase_pct:
                return RollbackCheckResult(
                    should_rollback=True,
                    reason=f"Latency increase {latency_increase_pct:.1f}% exceeds threshold "
                    f"{self.rollback_config.max_latency_increase_pct:.1f}% "
                    f"(control={control_latency:.0f}ms, treatment={treatment_latency:.0f}ms)",
                )

        # Check error rate increase
        control_error_rate = self.control_metrics.error_rate
        treatment_error_rate = self.treatment_metrics.error_rate
        error_rate_increase = treatment_error_rate - control_error_rate

        if error_rate_increase > self.rollback_config.max_error_rate_increase:
            return RollbackCheckResult(
                should_rollback=True,
                reason=f"Error rate increase {error_rate_increase:.1%} exceeds threshold "
                f"{self.rollback_config.max_error_rate_increase:.1%} "
                f"(control={control_error_rate:.1%}, treatment={treatment_error_rate:.1%})",
            )

        return RollbackCheckResult(
            should_rollback=False, reason="All metrics within acceptable bounds"
        )

    def get_metrics_summary(self) -> dict[str, Any]:
        """Get a summary of metrics for both groups.

        Returns:
            Dictionary with metrics for control and treatment groups
        """
        return {
            "control": {
                "fp_rate": self.control_metrics.fp_rate,
                "avg_latency_ms": self.control_metrics.avg_latency_ms,
                "avg_risk_score": self.control_metrics.avg_risk_score,
                "sample_count": self.control_metrics.total_feedback_count,
                "error_rate": self.control_metrics.error_rate,
                "analysis_count": self.control_metrics.total_analyses,
            },
            "treatment": {
                "fp_rate": self.treatment_metrics.fp_rate,
                "avg_latency_ms": self.treatment_metrics.avg_latency_ms,
                "avg_risk_score": self.treatment_metrics.avg_risk_score,
                "sample_count": self.treatment_metrics.total_feedback_count,
                "error_rate": self.treatment_metrics.error_rate,
                "analysis_count": self.treatment_metrics.total_analyses,
            },
            "experiment": {
                "name": self.rollout_config.experiment_name,
                "is_active": self.is_active,
                "is_expired": self.is_expired,
                "remaining_hours": self.remaining_hours,
                "started_at": (
                    self.rollout_config.started_at.isoformat()
                    if self.rollout_config.started_at
                    else None
                ),
            },
        }


# =============================================================================
# Module-level singleton for the rollout manager
# =============================================================================

_rollout_manager: ABRolloutManager | None = None


def get_rollout_manager() -> ABRolloutManager | None:
    """Get the global rollout manager instance.

    Returns:
        ABRolloutManager instance if configured, None otherwise
    """
    return _rollout_manager


def configure_rollout_manager(
    rollout_config: ABRolloutConfig | None = None,
    rollback_config: AutoRollbackConfig | None = None,
) -> ABRolloutManager:
    """Configure and return the global rollout manager.

    If no configs provided, uses defaults (50/50 split, 48 hours).

    Args:
        rollout_config: Optional A/B test configuration
        rollback_config: Optional auto-rollback configuration

    Returns:
        Configured ABRolloutManager instance
    """
    global _rollout_manager  # noqa: PLW0603

    if rollout_config is None:
        rollout_config = ABRolloutConfig()
    if rollback_config is None:
        rollback_config = AutoRollbackConfig()

    _rollout_manager = ABRolloutManager(
        rollout_config=rollout_config,
        rollback_config=rollback_config,
    )
    return _rollout_manager


def reset_rollout_manager() -> None:
    """Reset the global rollout manager (for testing)."""
    global _rollout_manager  # noqa: PLW0603
    _rollout_manager = None
