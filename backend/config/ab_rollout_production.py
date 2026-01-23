"""Production A/B Rollout Configuration for Phase 7.2 (NEM-3338).

This module provides the production configuration for the A/B testing rollout
of the new Nemotron prompt improvements. It configures:

1. **50/50 Traffic Split**: Equal distribution between control (V1) and treatment (V2)
2. **48-Hour Test Duration**: Sufficient time to collect statistically significant data
3. **Auto-Rollback Thresholds**: Automatic reversion if metrics degrade

Target Metrics:
- FP rate reduction from ~60% to <20%
- No significant latency increase (max +50%)
- No increase in error rate (max +5%)

Usage:
    from backend.config.ab_rollout_production import (
        start_production_ab_rollout,
        get_production_rollout_manager,
        stop_production_ab_rollout,
    )

    # Start the A/B test
    manager = start_production_ab_rollout()

    # During analysis, use the manager for group assignment
    group = manager.get_group_for_camera(camera_id)

    # Check for rollback conditions periodically
    result = manager.check_rollback_needed()
    if result.should_rollback:
        manager.stop()

    # Get metrics summary
    summary = manager.get_metrics_summary()
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.config.prompt_ab_rollout import (
    ABRolloutConfig,
    ABRolloutManager,
    AutoRollbackConfig,
    ExperimentGroup,
    configure_rollout_manager,
    get_rollout_manager,
    reset_rollout_manager,
)
from backend.core.logging import get_logger

if TYPE_CHECKING:
    from backend.config.prompt_ab_rollout import RollbackCheckResult

logger = get_logger(__name__)


# =============================================================================
# Production Configuration Constants
# =============================================================================

# Target: 50/50 traffic split for A/B test
PRODUCTION_TREATMENT_PERCENTAGE = 0.5

# Test duration: 48 hours to collect sufficient statistical data
PRODUCTION_TEST_DURATION_HOURS = 48

# Experiment name for tracking
PRODUCTION_EXPERIMENT_NAME = "nemotron_prompt_v2_phase7_2"

# Auto-rollback thresholds (conservative to protect user experience)
# Rollback if FP rate increases by more than 5 percentage points
MAX_FP_RATE_INCREASE = 0.05

# Rollback if latency increases by more than 50%
MAX_LATENCY_INCREASE_PCT = 50.0

# Rollback if error rate increases by more than 5 percentage points
MAX_ERROR_RATE_INCREASE = 0.05

# Minimum samples required before evaluating rollback conditions
# This prevents premature rollback due to statistical noise
MIN_SAMPLES_FOR_ROLLBACK = 100


# =============================================================================
# Production Configuration Functions
# =============================================================================


def create_production_rollout_config() -> ABRolloutConfig:
    """Create the production A/B rollout configuration.

    This configures a 50/50 traffic split for 48 hours between:
    - Control (V1): Current production prompt
    - Treatment (V2): New calibrated prompt with improved scoring

    Returns:
        ABRolloutConfig with production settings
    """
    return ABRolloutConfig(
        treatment_percentage=PRODUCTION_TREATMENT_PERCENTAGE,
        test_duration_hours=PRODUCTION_TEST_DURATION_HOURS,
        experiment_name=PRODUCTION_EXPERIMENT_NAME,
        started_at=None,  # Will be set when experiment starts
    )


def create_production_rollback_config() -> AutoRollbackConfig:
    """Create the production auto-rollback configuration.

    This configures automatic rollback if the treatment group shows:
    - FP rate increase > 5%
    - Latency increase > 50%
    - Error rate increase > 5%

    Rollback is only triggered after MIN_SAMPLES_FOR_ROLLBACK samples
    have been collected in each group.

    Returns:
        AutoRollbackConfig with production settings
    """
    return AutoRollbackConfig(
        max_fp_rate_increase=MAX_FP_RATE_INCREASE,
        max_latency_increase_pct=MAX_LATENCY_INCREASE_PCT,
        max_error_rate_increase=MAX_ERROR_RATE_INCREASE,
        min_samples=MIN_SAMPLES_FOR_ROLLBACK,
        enabled=True,
    )


def start_production_ab_rollout() -> ABRolloutManager:
    """Start the production A/B rollout experiment.

    Creates and configures the global rollout manager with production
    settings, then starts the experiment. The experiment will run for
    48 hours with 50/50 traffic split.

    The manager tracks:
    - FP rate per group (via user feedback)
    - Risk score distributions per group
    - Latency per group
    - Error rate per group

    Auto-rollback will trigger if treatment performance degrades.

    Returns:
        Configured and started ABRolloutManager instance

    Example:
        manager = start_production_ab_rollout()
        print(f"Experiment started: {manager.rollout_config.experiment_name}")
        print(f"Duration: {manager.rollout_config.test_duration_hours} hours")
    """
    # Reset any existing manager
    reset_rollout_manager()

    # Create production configuration
    rollout_config = create_production_rollout_config()
    rollback_config = create_production_rollback_config()

    # Configure global manager
    manager = configure_rollout_manager(
        rollout_config=rollout_config,
        rollback_config=rollback_config,
    )

    # Start the experiment
    manager.start()

    logger.info(
        f"Production A/B rollout started: "
        f"experiment={rollout_config.experiment_name}, "
        f"treatment={rollout_config.treatment_percentage:.0%}, "
        f"duration={rollout_config.test_duration_hours}h, "
        f"auto_rollback={rollback_config.enabled}"
    )

    return manager


def get_production_rollout_manager() -> ABRolloutManager | None:
    """Get the global production rollout manager.

    Returns:
        ABRolloutManager instance if configured, None otherwise
    """
    return get_rollout_manager()


def stop_production_ab_rollout(reason: str = "Manual stop") -> bool:
    """Stop the production A/B rollout experiment.

    Args:
        reason: Reason for stopping the experiment

    Returns:
        True if experiment was stopped, False if no experiment was active
    """
    manager = get_rollout_manager()
    if manager is None:
        logger.warning("No production A/B rollout to stop")
        return False

    if not manager.is_active:
        logger.warning("Production A/B rollout was not active")
        return False

    manager.stop()
    logger.info(f"Production A/B rollout stopped: reason={reason}")

    return True


def check_and_handle_rollback() -> RollbackCheckResult:
    """Check if rollback is needed and handle if so.

    This function should be called periodically during the experiment
    to check if auto-rollback conditions are met.

    Returns:
        RollbackCheckResult indicating whether rollback occurred

    Raises:
        RuntimeError: If no rollout manager is configured
    """
    from backend.config.prompt_ab_rollout import RollbackCheckResult

    manager = get_rollout_manager()
    if manager is None:
        return RollbackCheckResult(should_rollback=False, reason="No rollout manager configured")

    result = manager.check_rollback_needed()

    if result.should_rollback:
        logger.warning(f"Auto-rollback triggered: reason={result.reason}")
        manager.stop()

        # Log metrics at time of rollback
        summary = manager.get_metrics_summary()
        logger.info(
            f"Rollback metrics: control_fp={summary['control']['fp_rate']:.1%}, "
            f"treatment_fp={summary['treatment']['fp_rate']:.1%}, "
            f"control_samples={summary['control']['sample_count']}, "
            f"treatment_samples={summary['treatment']['sample_count']}"
        )

    return result


def get_experiment_status() -> dict:
    """Get the current status of the A/B rollout experiment.

    Returns a dictionary with:
    - is_active: Whether experiment is running
    - is_expired: Whether experiment duration has elapsed
    - remaining_hours: Hours remaining in the experiment
    - metrics: Summary of control and treatment metrics
    - config: Current experiment configuration

    Returns:
        Dictionary with experiment status
    """
    manager = get_rollout_manager()
    if manager is None:
        return {
            "is_active": False,
            "is_expired": False,
            "remaining_hours": 0,
            "metrics": None,
            "config": None,
            "message": "No A/B rollout experiment configured",
        }

    summary = manager.get_metrics_summary()

    return {
        "is_active": manager.is_active,
        "is_expired": manager.is_expired,
        "remaining_hours": manager.remaining_hours,
        "metrics": {
            "control": {
                "fp_rate": summary["control"]["fp_rate"],
                "avg_latency_ms": summary["control"]["avg_latency_ms"],
                "avg_risk_score": summary["control"]["avg_risk_score"],
                "sample_count": summary["control"]["sample_count"],
                "analysis_count": summary["control"]["analysis_count"],
                "error_rate": summary["control"]["error_rate"],
            },
            "treatment": {
                "fp_rate": summary["treatment"]["fp_rate"],
                "avg_latency_ms": summary["treatment"]["avg_latency_ms"],
                "avg_risk_score": summary["treatment"]["avg_risk_score"],
                "sample_count": summary["treatment"]["sample_count"],
                "analysis_count": summary["treatment"]["analysis_count"],
                "error_rate": summary["treatment"]["error_rate"],
            },
        },
        "config": {
            "experiment_name": manager.rollout_config.experiment_name,
            "treatment_percentage": manager.rollout_config.treatment_percentage,
            "test_duration_hours": manager.rollout_config.test_duration_hours,
            "started_at": (
                manager.rollout_config.started_at.isoformat()
                if manager.rollout_config.started_at
                else None
            ),
        },
        "rollback_config": {
            "enabled": manager.rollback_config.enabled,
            "max_fp_rate_increase": manager.rollback_config.max_fp_rate_increase,
            "max_latency_increase_pct": manager.rollback_config.max_latency_increase_pct,
            "max_error_rate_increase": manager.rollback_config.max_error_rate_increase,
            "min_samples": manager.rollback_config.min_samples,
        },
    }


def get_camera_assignment(camera_id: str) -> dict:
    """Get the experiment group assignment for a camera.

    Args:
        camera_id: Camera identifier

    Returns:
        Dictionary with:
        - camera_id: The camera ID
        - group: ExperimentGroup (CONTROL or TREATMENT)
        - prompt_version: Which prompt version will be used
        - message: Human-readable assignment description
    """
    from backend.config.prompt_experiment import PromptVersion

    manager = get_rollout_manager()
    if manager is None:
        return {
            "camera_id": camera_id,
            "group": None,
            "prompt_version": PromptVersion.V1_ORIGINAL.value,
            "message": "No A/B rollout active - using V1 (control)",
        }

    group = manager.get_group_for_camera(camera_id)
    prompt_version = (
        PromptVersion.V2_CALIBRATED
        if group == ExperimentGroup.TREATMENT
        else PromptVersion.V1_ORIGINAL
    )

    return {
        "camera_id": camera_id,
        "group": group.value,
        "prompt_version": prompt_version.value,
        "message": (f"Camera assigned to {group.value} group - using {prompt_version.value}"),
    }


# =============================================================================
# Module-level Exports
# =============================================================================

__all__ = [
    "MAX_ERROR_RATE_INCREASE",
    "MAX_FP_RATE_INCREASE",
    "MAX_LATENCY_INCREASE_PCT",
    "MIN_SAMPLES_FOR_ROLLBACK",
    "PRODUCTION_EXPERIMENT_NAME",
    "PRODUCTION_TEST_DURATION_HOURS",
    "PRODUCTION_TREATMENT_PERCENTAGE",
    "check_and_handle_rollback",
    "create_production_rollback_config",
    "create_production_rollout_config",
    "get_camera_assignment",
    "get_experiment_status",
    "get_production_rollout_manager",
    "start_production_ab_rollout",
    "stop_production_ab_rollout",
]
