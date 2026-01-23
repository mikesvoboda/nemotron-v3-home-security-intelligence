"""Backend configuration modules.

This package contains configuration classes for various backend features
including A/B testing experiments, prompt version management, shadow
mode deployment for prompt comparison testing, and A/B rollout management
for phased prompt deployments.
"""

from backend.config.ab_rollout_production import (
    MAX_ERROR_RATE_INCREASE,
    MAX_FP_RATE_INCREASE,
    MAX_LATENCY_INCREASE_PCT,
    MIN_SAMPLES_FOR_ROLLBACK,
    PRODUCTION_EXPERIMENT_NAME,
    PRODUCTION_TEST_DURATION_HOURS,
    PRODUCTION_TREATMENT_PERCENTAGE,
    check_and_handle_rollback,
    create_production_rollback_config,
    create_production_rollout_config,
    get_camera_assignment,
    get_experiment_status,
    get_production_rollout_manager,
    start_production_ab_rollout,
    stop_production_ab_rollout,
)
from backend.config.prompt_ab_rollout import (
    ABRolloutConfig,
    ABRolloutManager,
    AutoRollbackConfig,
    ExperimentGroup,
    GroupMetrics,
    RollbackCheckResult,
    configure_rollout_manager,
    get_rollout_manager,
    reset_rollout_manager,
)
from backend.config.prompt_experiment import (
    PromptExperimentConfig,
    PromptVersion,
    get_prompt_experiment_config,
    reset_prompt_experiment_config,
)
from backend.config.shadow_mode_deployment import (
    LatencyWarning,
    ShadowModeComparisonResult,
    ShadowModeComparisonStats,
    ShadowModeDeploymentConfig,
    ShadowModeStatsTracker,
    create_deployment_from_experiment_config,
    get_shadow_mode_deployment_config,
    get_shadow_mode_stats,
    get_shadow_mode_stats_tracker,
    record_and_track_shadow_comparison,
    record_latency_warning,
    record_shadow_mode_comparison,
    reset_shadow_mode_deployment_config,
    reset_shadow_mode_stats_tracker,
)

__all__ = [
    # Production A/B rollout config (NEM-3338 Phase 7.2)
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
    # A/B rollout config (NEM-3338)
    "ABRolloutConfig",
    "ABRolloutManager",
    "AutoRollbackConfig",
    "ExperimentGroup",
    "GroupMetrics",
    "RollbackCheckResult",
    "configure_rollout_manager",
    "get_rollout_manager",
    "reset_rollout_manager",
    # Prompt experiment config
    "PromptExperimentConfig",
    "PromptVersion",
    "get_prompt_experiment_config",
    "reset_prompt_experiment_config",
    # Shadow mode deployment config
    "LatencyWarning",
    "ShadowModeComparisonResult",
    "ShadowModeComparisonStats",
    "ShadowModeDeploymentConfig",
    "ShadowModeStatsTracker",
    "create_deployment_from_experiment_config",
    "get_shadow_mode_deployment_config",
    "get_shadow_mode_stats",
    "get_shadow_mode_stats_tracker",
    "record_and_track_shadow_comparison",
    "record_latency_warning",
    "record_shadow_mode_comparison",
    "reset_shadow_mode_deployment_config",
    "reset_shadow_mode_stats_tracker",
]
