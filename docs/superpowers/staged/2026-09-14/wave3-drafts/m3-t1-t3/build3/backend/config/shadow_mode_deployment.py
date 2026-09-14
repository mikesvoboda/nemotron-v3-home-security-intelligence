"""Shadow Mode Deployment Configuration for Prompt A/B Testing (NEM-3337).

This module provides configuration for shadow mode deployment of new prompts.
In shadow mode, both control (v1) and treatment (v2) prompts run in parallel,
but only control results are used for actual risk scoring. Treatment results
are logged for comparison analysis without affecting users.

Shadow Mode Flow:
1. Receive detection batch for analysis
2. Run control (v1) prompt - result is used as actual output
3. Run treatment (v2) prompt in parallel - result is logged only
4. Compare results: risk scores, latency, errors
5. Log comparison metrics for analysis
6. If treatment latency exceeds threshold (default 50%), trigger warning

Metrics Tracked:
- Risk score distribution comparison (control vs treatment)
- Latency comparison (ms and percentage difference)
- Error rate comparison
- Memory usage (optional)

Integration:
- Uses PromptExperimentConfig for experiment settings
- Records metrics via Prometheus (backend.core.metrics)
- Logs via structured logging (backend.core.logging)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class LatencyWarning:
    """Result of a latency warning check.

    Attributes:
        triggered: Whether the warning threshold was exceeded
        percentage_increase: Percentage increase of treatment over control
        message: Human-readable warning message
        control_latency_ms: Control prompt latency in milliseconds
        treatment_latency_ms: Treatment prompt latency in milliseconds
        threshold_pct: The threshold that was checked against
    """

    triggered: bool
    percentage_increase: float
    message: str
    control_latency_ms: float
    treatment_latency_ms: float
    threshold_pct: float


@dataclass
class ShadowModeComparisonResult:
    """Result of a shadow mode comparison between control and treatment prompts.

    Attributes:
        control_risk_score: Risk score from control (v1) prompt
        treatment_risk_score: Risk score from treatment (v2) prompt (None if failed)
        control_latency_ms: Control prompt latency in milliseconds
        treatment_latency_ms: Treatment prompt latency in milliseconds (None if failed)
        risk_score_diff: Absolute difference in risk scores (None if treatment failed)
        latency_diff_ms: Difference in latency (treatment - control) in ms
        latency_increase_pct: Percentage increase in latency (None if control was 0)
        latency_warning_triggered: Whether latency exceeded warning threshold
        timestamp: ISO timestamp of the comparison
        camera_id: Optional camera identifier for filtering
        control_error: Error message if control prompt failed
        treatment_error: Error message if treatment prompt failed
    """

    control_risk_score: int | None
    treatment_risk_score: int | None
    control_latency_ms: float | None
    treatment_latency_ms: float | None
    risk_score_diff: int | None
    latency_diff_ms: float | None
    latency_increase_pct: float | None
    latency_warning_triggered: bool
    timestamp: str
    camera_id: str | None = None
    control_error: str | None = None
    treatment_error: str | None = None


@dataclass
class ShadowModeDeploymentConfig:
    """Configuration for shadow mode deployment of prompt versions.

    This configuration controls how shadow mode comparison runs:
    - Both prompts execute in parallel
    - Control result is used as the actual output
    - Treatment result is logged for comparison only
    - Metrics track risk score and latency differences
    - Warning triggered if treatment is too slow

    Attributes:
        enabled: Whether shadow mode is active
        control_prompt_name: Name/version of the control prompt
        treatment_prompt_name: Name/version of the treatment prompt
        log_comparisons: Whether to log comparison results
        latency_warning_threshold_pct: Latency increase % that triggers warning
        experiment_name: Name of the experiment for tracking
        track_risk_score_diff: Whether to track risk score differences
        track_latency_diff: Whether to track latency differences
        track_memory_usage: Whether to track memory usage
        track_error_rate: Whether to track error rates
        run_both_prompts: Whether both prompts run (always True in shadow mode)
        primary_result_source: Which result to use as primary ("control")
        treatment_result_usage: How treatment result is used ("comparison_only")

    Example:
        # Create shadow mode deployment for testing new prompts
        config = ShadowModeDeploymentConfig(
            enabled=True,
            control_prompt_name="v1_original",
            treatment_prompt_name="v2_calibrated",
            latency_warning_threshold_pct=50.0,
        )

        # Check if latency warning should trigger
        warning = config.check_latency_warning(
            control_latency_ms=100.0,
            treatment_latency_ms=160.0,
        )
        if warning.triggered:
            logger.warning(warning.message)
    """

    # Core configuration
    enabled: bool = True
    control_prompt_name: str = "v1_original"
    treatment_prompt_name: str = "v2_calibrated"
    log_comparisons: bool = True
    latency_warning_threshold_pct: float = 50.0
    experiment_name: str = "nemotron_prompt_v2_shadow"

    # Metrics tracking configuration
    track_risk_score_diff: bool = True
    track_latency_diff: bool = True
    track_memory_usage: bool = False  # Optional, may impact performance
    track_error_rate: bool = True

    # Shadow mode behavior (these are fixed for shadow mode)
    run_both_prompts: bool = field(default=True, init=False)
    primary_result_source: str = field(default="control", init=False)
    treatment_result_usage: str = field(default="comparison_only", init=False)

    def __post_init__(self) -> None:
        """Validate configuration values after initialization."""
        if self.latency_warning_threshold_pct < 0:
            raise ValueError(
                f"latency_warning_threshold_pct must be non-negative, "
                f"got {self.latency_warning_threshold_pct}"
            )

    def check_latency_warning(
        self,
        control_latency_ms: float,
        treatment_latency_ms: float,
    ) -> LatencyWarning:
        """Check if treatment latency exceeds the warning threshold.

        Args:
            control_latency_ms: Control prompt latency in milliseconds
            treatment_latency_ms: Treatment prompt latency in milliseconds

        Returns:
            LatencyWarning with check results
        """
        # Handle edge case of zero control latency
        if control_latency_ms <= 0:
            # When control is effectively instant, any treatment time is considered
            # We don't trigger warning for this edge case, but log it
            return LatencyWarning(
                triggered=False,
                percentage_increase=float("inf") if treatment_latency_ms > 0 else 0.0,
                message="Control latency is zero, cannot calculate percentage increase",
                control_latency_ms=control_latency_ms,
                treatment_latency_ms=treatment_latency_ms,
                threshold_pct=self.latency_warning_threshold_pct,
            )

        # Calculate percentage increase
        latency_diff = treatment_latency_ms - control_latency_ms
        percentage_increase = (latency_diff / control_latency_ms) * 100.0

        # Check if threshold exceeded
        triggered = percentage_increase > self.latency_warning_threshold_pct

        if triggered:
            message = (
                f"Treatment latency ({treatment_latency_ms:.1f}ms) exceeds control "
                f"({control_latency_ms:.1f}ms) by {percentage_increase:.1f}%, "
                f"which exceeds the {self.latency_warning_threshold_pct:.1f}% threshold"
            )
        else:
            message = (
                f"Treatment latency ({treatment_latency_ms:.1f}ms) is within "
                f"acceptable range ({percentage_increase:.1f}% vs {self.latency_warning_threshold_pct:.1f}% threshold)"
            )

        return LatencyWarning(
            triggered=triggered,
            percentage_increase=percentage_increase,
            message=message,
            control_latency_ms=control_latency_ms,
            treatment_latency_ms=treatment_latency_ms,
            threshold_pct=self.latency_warning_threshold_pct,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize configuration to dictionary.

        Returns:
            Dictionary representation of the configuration
        """
        return {
            "enabled": self.enabled,
            "control_prompt_name": self.control_prompt_name,
            "treatment_prompt_name": self.treatment_prompt_name,
            "log_comparisons": self.log_comparisons,
            "latency_warning_threshold_pct": self.latency_warning_threshold_pct,
            "experiment_name": self.experiment_name,
            "track_risk_score_diff": self.track_risk_score_diff,
            "track_latency_diff": self.track_latency_diff,
            "track_memory_usage": self.track_memory_usage,
            "track_error_rate": self.track_error_rate,
            "run_both_prompts": self.run_both_prompts,
            "primary_result_source": self.primary_result_source,
            "treatment_result_usage": self.treatment_result_usage,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ShadowModeDeploymentConfig:
        """Create configuration from dictionary.

        Args:
            data: Dictionary with configuration fields

        Returns:
            ShadowModeDeploymentConfig instance
        """
        return cls(
            enabled=data.get("enabled", True),
            control_prompt_name=data.get("control_prompt_name", "v1_original"),
            treatment_prompt_name=data.get("treatment_prompt_name", "v2_calibrated"),
            log_comparisons=data.get("log_comparisons", True),
            latency_warning_threshold_pct=data.get("latency_warning_threshold_pct", 50.0),
            experiment_name=data.get("experiment_name", "nemotron_prompt_v2_shadow"),
            track_risk_score_diff=data.get("track_risk_score_diff", True),
            track_latency_diff=data.get("track_latency_diff", True),
            track_memory_usage=data.get("track_memory_usage", False),
            track_error_rate=data.get("track_error_rate", True),
        )


def create_deployment_from_experiment_config(
    experiment_config: Any,
) -> ShadowModeDeploymentConfig:
    """Create a shadow mode deployment config from an experiment config.

    This factory function creates a ShadowModeDeploymentConfig that integrates
    with the existing PromptExperimentConfig infrastructure.

    Args:
        experiment_config: PromptExperimentConfig instance

    Returns:
        ShadowModeDeploymentConfig configured from experiment settings
    """
    return ShadowModeDeploymentConfig(
        enabled=experiment_config.shadow_mode,
        experiment_name=experiment_config.experiment_name,
        latency_warning_threshold_pct=experiment_config.max_latency_increase_pct,
    )


def record_shadow_mode_comparison(result: ShadowModeComparisonResult) -> None:
    """Record shadow mode comparison metrics to Prometheus.

    This function records comprehensive metrics for analyzing shadow mode
    prompt comparisons, including:
    - Risk score distributions for both control and treatment
    - Risk score difference histogram
    - Risk level shift direction (lower/same/higher)
    - Latency difference histogram
    - Latency warnings when threshold exceeded
    - Error tracking for failed comparisons

    Args:
        result: Comparison result to record
    """
    from backend.core.metrics import (
        record_shadow_comparison,
        record_shadow_comparison_error,
        record_shadow_latency_diff,
        record_shadow_latency_warning,
        record_shadow_risk_level_shift,
        record_shadow_risk_score,
        record_shadow_risk_score_diff,
    )

    # Record the shadow comparison counter
    record_shadow_comparison("nemotron")

    # Handle error cases
    if result.control_error and result.treatment_error:
        record_shadow_comparison_error("both_failed")
    elif result.control_error:
        record_shadow_comparison_error("control_failed")
    elif result.treatment_error:
        record_shadow_comparison_error("treatment_failed")

    # Record risk score distributions
    if result.control_risk_score is not None:
        record_shadow_risk_score("control", result.control_risk_score)

    if result.treatment_risk_score is not None:
        record_shadow_risk_score("treatment", result.treatment_risk_score)

    # Record risk score difference if both scores available
    if result.risk_score_diff is not None:
        record_shadow_risk_score_diff(result.risk_score_diff)

        # Determine and record risk level shift direction
        if result.control_risk_score is not None and result.treatment_risk_score is not None:
            if result.treatment_risk_score < result.control_risk_score:
                record_shadow_risk_level_shift("lower")
            elif result.treatment_risk_score > result.control_risk_score:
                record_shadow_risk_level_shift("higher")
            else:
                record_shadow_risk_level_shift("same")

    # Record latency difference if both latencies available
    if result.latency_diff_ms is not None:
        record_shadow_latency_diff(result.latency_diff_ms / 1000.0)  # Convert to seconds

    # Record latency warning if triggered
    if result.latency_warning_triggered:
        record_shadow_latency_warning("nemotron")

    # Log detailed comparison for analysis
    logger.info(
        "Shadow mode comparison completed",
        extra={
            "camera_id": result.camera_id,
            "control_risk_score": result.control_risk_score,
            "treatment_risk_score": result.treatment_risk_score,
            "risk_score_diff": result.risk_score_diff,
            "control_latency_ms": result.control_latency_ms,
            "treatment_latency_ms": result.treatment_latency_ms,
            "latency_diff_ms": result.latency_diff_ms,
            "latency_increase_pct": result.latency_increase_pct,
            "latency_warning_triggered": result.latency_warning_triggered,
            "control_error": result.control_error,
            "treatment_error": result.treatment_error,
        },
    )


def record_latency_warning(
    camera_id: str,
    control_latency_ms: float,
    treatment_latency_ms: float,
    threshold_pct: float,
) -> None:
    """Record a latency warning event when threshold is exceeded.

    Args:
        camera_id: Camera identifier
        control_latency_ms: Control prompt latency
        treatment_latency_ms: Treatment prompt latency
        threshold_pct: The threshold that was exceeded
    """
    from backend.core.metrics import record_prompt_latency

    # Record latencies for both versions
    record_prompt_latency("v1_control", control_latency_ms / 1000.0)
    record_prompt_latency("v2_treatment", treatment_latency_ms / 1000.0)

    # Log the warning
    latency_increase_pct = (
        ((treatment_latency_ms - control_latency_ms) / control_latency_ms * 100.0)
        if control_latency_ms > 0
        else float("inf")
    )

    logger.warning(
        "Shadow mode latency warning triggered",
        extra={
            "camera_id": camera_id,
            "control_latency_ms": control_latency_ms,
            "treatment_latency_ms": treatment_latency_ms,
            "latency_increase_pct": latency_increase_pct,
            "threshold_pct": threshold_pct,
        },
    )


@dataclass
class ShadowModeComparisonStats:
    """Rolling statistics for shadow mode comparisons.

    Tracks aggregate statistics over a window of comparisons to
    provide insights into risk distribution differences between
    control and treatment prompts.

    Attributes:
        total_comparisons: Total number of comparisons
        control_avg_score: Rolling average control risk score
        treatment_avg_score: Rolling average treatment risk score
        avg_score_diff: Average absolute difference in risk scores
        lower_count: Count of comparisons where treatment was lower risk
        same_count: Count of comparisons where treatment was same risk
        higher_count: Count of comparisons where treatment was higher risk
        latency_warnings: Count of latency warnings triggered
        control_errors: Count of control prompt errors
        treatment_errors: Count of treatment prompt errors
    """

    total_comparisons: int = 0
    control_avg_score: float = 0.0
    treatment_avg_score: float = 0.0
    avg_score_diff: float = 0.0
    lower_count: int = 0
    same_count: int = 0
    higher_count: int = 0
    latency_warnings: int = 0
    control_errors: int = 0
    treatment_errors: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize statistics to dictionary.

        Returns:
            Dictionary representation of the statistics
        """
        return {
            "total_comparisons": self.total_comparisons,
            "control_avg_score": round(self.control_avg_score, 2),
            "treatment_avg_score": round(self.treatment_avg_score, 2),
            "avg_score_diff": round(self.avg_score_diff, 2),
            "risk_shift_distribution": {
                "lower": self.lower_count,
                "same": self.same_count,
                "higher": self.higher_count,
            },
            "lower_percentage": (
                round(self.lower_count / self.total_comparisons * 100, 1)
                if self.total_comparisons > 0
                else 0.0
            ),
            "latency_warnings": self.latency_warnings,
            "error_rates": {
                "control": self.control_errors,
                "treatment": self.treatment_errors,
            },
        }


class ShadowModeStatsTracker:
    """Tracks rolling statistics for shadow mode comparisons.

    This tracker maintains aggregate statistics for analyzing
    the performance difference between control and treatment prompts.
    Statistics are updated incrementally with each comparison.

    Example:
        tracker = ShadowModeStatsTracker()
        tracker.record(result)  # ShadowModeComparisonResult
        stats = tracker.get_stats()
        print(f"Treatment avg score: {stats.treatment_avg_score}")
    """

    def __init__(self) -> None:
        """Initialize the stats tracker."""
        self._total_comparisons = 0
        self._control_score_sum = 0.0
        self._treatment_score_sum = 0.0
        self._score_diff_sum = 0.0
        self._lower_count = 0
        self._same_count = 0
        self._higher_count = 0
        self._latency_warnings = 0
        self._control_errors = 0
        self._treatment_errors = 0
        self._control_valid_count = 0
        self._treatment_valid_count = 0
        self._diff_valid_count = 0

    def record(self, result: ShadowModeComparisonResult) -> None:
        """Record a comparison result and update statistics.

        Args:
            result: Comparison result to record
        """
        self._total_comparisons += 1

        # Update error counts
        if result.control_error:
            self._control_errors += 1
        if result.treatment_error:
            self._treatment_errors += 1

        # Update risk score sums for averages
        if result.control_risk_score is not None:
            self._control_score_sum += result.control_risk_score
            self._control_valid_count += 1

        if result.treatment_risk_score is not None:
            self._treatment_score_sum += result.treatment_risk_score
            self._treatment_valid_count += 1

        # Update score diff and shift direction
        if result.risk_score_diff is not None:
            self._score_diff_sum += result.risk_score_diff
            self._diff_valid_count += 1

            if result.control_risk_score is not None and result.treatment_risk_score is not None:
                if result.treatment_risk_score < result.control_risk_score:
                    self._lower_count += 1
                elif result.treatment_risk_score > result.control_risk_score:
                    self._higher_count += 1
                else:
                    self._same_count += 1

        # Update latency warning count
        if result.latency_warning_triggered:
            self._latency_warnings += 1

        # Update Prometheus gauges for average scores
        self._update_prometheus_gauges()

    def _update_prometheus_gauges(self) -> None:
        """Update Prometheus gauge metrics with current averages."""
        from backend.core.metrics import update_shadow_avg_risk_score

        if self._control_valid_count > 0:
            control_avg = self._control_score_sum / self._control_valid_count
            update_shadow_avg_risk_score("control", control_avg)

        if self._treatment_valid_count > 0:
            treatment_avg = self._treatment_score_sum / self._treatment_valid_count
            update_shadow_avg_risk_score("treatment", treatment_avg)

    def get_stats(self) -> ShadowModeComparisonStats:
        """Get the current aggregate statistics.

        Returns:
            ShadowModeComparisonStats with current values
        """
        control_avg = (
            self._control_score_sum / self._control_valid_count
            if self._control_valid_count > 0
            else 0.0
        )
        treatment_avg = (
            self._treatment_score_sum / self._treatment_valid_count
            if self._treatment_valid_count > 0
            else 0.0
        )
        avg_diff = (
            self._score_diff_sum / self._diff_valid_count if self._diff_valid_count > 0 else 0.0
        )

        return ShadowModeComparisonStats(
            total_comparisons=self._total_comparisons,
            control_avg_score=control_avg,
            treatment_avg_score=treatment_avg,
            avg_score_diff=avg_diff,
            lower_count=self._lower_count,
            same_count=self._same_count,
            higher_count=self._higher_count,
            latency_warnings=self._latency_warnings,
            control_errors=self._control_errors,
            treatment_errors=self._treatment_errors,
        )

    def reset(self) -> None:
        """Reset all statistics to initial values."""
        self._total_comparisons = 0
        self._control_score_sum = 0.0
        self._treatment_score_sum = 0.0
        self._score_diff_sum = 0.0
        self._lower_count = 0
        self._same_count = 0
        self._higher_count = 0
        self._latency_warnings = 0
        self._control_errors = 0
        self._treatment_errors = 0
        self._control_valid_count = 0
        self._treatment_valid_count = 0
        self._diff_valid_count = 0


# Module-level singletons
_shadow_mode_deployment_config: ShadowModeDeploymentConfig | None = None
_shadow_mode_stats_tracker: ShadowModeStatsTracker | None = None


def get_shadow_mode_deployment_config() -> ShadowModeDeploymentConfig:
    """Get the global shadow mode deployment configuration singleton.

    Returns:
        ShadowModeDeploymentConfig instance with current settings
    """
    global _shadow_mode_deployment_config  # noqa: PLW0603
    if _shadow_mode_deployment_config is None:
        _shadow_mode_deployment_config = ShadowModeDeploymentConfig()
    return _shadow_mode_deployment_config


def reset_shadow_mode_deployment_config() -> None:
    """Reset the shadow mode deployment configuration singleton.

    This is primarily used for testing to ensure clean state between tests.
    """
    global _shadow_mode_deployment_config  # noqa: PLW0603
    _shadow_mode_deployment_config = None


def get_shadow_mode_stats_tracker() -> ShadowModeStatsTracker:
    """Get the global shadow mode stats tracker singleton.

    Returns:
        ShadowModeStatsTracker instance for tracking comparison statistics
    """
    global _shadow_mode_stats_tracker  # noqa: PLW0603
    if _shadow_mode_stats_tracker is None:
        _shadow_mode_stats_tracker = ShadowModeStatsTracker()
    return _shadow_mode_stats_tracker


def reset_shadow_mode_stats_tracker() -> None:
    """Reset the shadow mode stats tracker singleton.

    This is primarily used for testing to ensure clean state between tests.
    """
    global _shadow_mode_stats_tracker  # noqa: PLW0603
    _shadow_mode_stats_tracker = None


def record_and_track_shadow_comparison(result: ShadowModeComparisonResult) -> None:
    """Record shadow mode comparison metrics and track statistics.

    This is a convenience function that both records the comparison
    to Prometheus metrics and updates the rolling statistics tracker.

    Args:
        result: Comparison result to record and track
    """
    record_shadow_mode_comparison(result)
    get_shadow_mode_stats_tracker().record(result)


def get_shadow_mode_stats() -> ShadowModeComparisonStats:
    """Get the current shadow mode comparison statistics.

    Returns:
        ShadowModeComparisonStats with aggregate statistics
    """
    return get_shadow_mode_stats_tracker().get_stats()
