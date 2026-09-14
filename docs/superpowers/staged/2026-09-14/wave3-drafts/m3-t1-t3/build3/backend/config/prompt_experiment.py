"""Prompt Experiment Configuration for A/B Testing (NEM-3023).

This module provides configuration for safely deploying new prompts using
shadow mode and A/B testing infrastructure. The experiment flow is:

1. Shadow Mode: Run both v1 and v2 prompts, but only use v1 results.
   This allows collecting comparison data without affecting users.

2. A/B Testing: Once shadow mode validates performance, gradually roll out
   v2 to a percentage of cameras using hash-based assignment for consistency.

3. Full Rollout: After A/B test validation, set treatment_percentage=1.0
   to deploy v2 to all cameras.

Camera-consistent assignment ensures the same camera always gets the same
prompt version, which is important for:
- Consistent user experience per camera
- Valid A/B test statistical analysis
- Reproducible debugging and troubleshooting

Auto-rollback thresholds trigger automatic reversion to v1 if:
- Latency increases beyond max_latency_increase_pct
- False positive reduction is below min_fp_reduction_pct
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class PromptVersion(Enum):
    """Enumeration of prompt versions for A/B testing.

    Attributes:
        V1_ORIGINAL: The current production prompt (control)
        V2_CALIBRATED: The new calibrated prompt with improved scoring (treatment)
    """

    V1_ORIGINAL = "v1_original"
    V2_CALIBRATED = "v2_calibrated"


@dataclass
class PromptExperimentConfig:
    """Configuration for prompt A/B testing and shadow mode.

    This config controls how prompt versions are selected for analysis.
    In shadow mode, both prompts run but only v1 results are used.
    In A/B test mode, cameras are consistently assigned to versions
    based on a hash of their camera_id.

    Attributes:
        shadow_mode: When True, run both prompts but only use v1 results.
            Shadow mode is used to collect comparison data without affecting users.
        treatment_percentage: Fraction of cameras to assign to v2 (0.0 to 1.0).
            Only used when shadow_mode is False.
        max_latency_increase_pct: Maximum allowed latency increase percentage
            before triggering automatic rollback (default: 50%).
        min_fp_reduction_pct: Minimum expected false positive reduction
            to consider v2 successful (default: 10%).
        experiment_name: Name of the experiment for tracking/logging.
        started_at: ISO timestamp when experiment started, or None if not started.

    Example:
        # Shadow mode - collect data without affecting users
        config = PromptExperimentConfig(shadow_mode=True)

        # A/B test with 30% treatment
        config = PromptExperimentConfig(
            shadow_mode=False,
            treatment_percentage=0.3,
        )

        # Full rollout of v2
        config = PromptExperimentConfig(
            shadow_mode=False,
            treatment_percentage=1.0,
        )
    """

    # Shadow mode: run both, only use v1 results
    shadow_mode: bool = True

    # A/B test split (0.0 = all v1, 1.0 = all v2)
    treatment_percentage: float = 0.0

    # Auto-rollback thresholds
    max_latency_increase_pct: float = 50.0  # Rollback if latency +50%
    min_fp_reduction_pct: float = 10.0  # Expect at least 10% FP reduction

    # Experiment tracking
    experiment_name: str = "nemotron_prompt_v2"
    started_at: str | None = None

    def __post_init__(self) -> None:
        """Validate configuration values after initialization."""
        if not 0.0 <= self.treatment_percentage <= 1.0:
            raise ValueError(
                f"treatment_percentage must be between 0.0 and 1.0, got {self.treatment_percentage}"
            )

    def get_version_for_camera(self, camera_id: str) -> PromptVersion:
        """Determine which prompt version to use for a camera.

        In shadow mode, always returns V1_ORIGINAL since shadow mode
        runs both prompts but only uses v1 results.

        In A/B test mode (shadow_mode=False), uses a hash of the camera_id
        to consistently assign cameras to versions based on treatment_percentage.

        Args:
            camera_id: Camera identifier for consistent assignment

        Returns:
            PromptVersion to use for this camera
        """
        if self.shadow_mode:
            # Shadow mode always uses v1 for actual results
            return PromptVersion.V1_ORIGINAL

        # Hash-based assignment for A/B test consistency
        # Using hash() gives deterministic assignment per camera_id
        hash_val = hash(camera_id) % 100
        if hash_val < self.treatment_percentage * 100:
            return PromptVersion.V2_CALIBRATED
        return PromptVersion.V1_ORIGINAL

    @property
    def is_shadow_mode(self) -> bool:
        """Check if shadow mode is enabled.

        Returns:
            True if shadow mode is active
        """
        return self.shadow_mode

    @property
    def is_ab_test_active(self) -> bool:
        """Check if an A/B test is currently active.

        An A/B test is active when:
        - Shadow mode is disabled
        - Treatment percentage is greater than 0

        Returns:
            True if A/B test is active
        """
        return not self.shadow_mode and self.treatment_percentage > 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize config to dictionary.

        Returns:
            Dictionary representation of the config
        """
        return {
            "shadow_mode": self.shadow_mode,
            "treatment_percentage": self.treatment_percentage,
            "max_latency_increase_pct": self.max_latency_increase_pct,
            "min_fp_reduction_pct": self.min_fp_reduction_pct,
            "experiment_name": self.experiment_name,
            "started_at": self.started_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PromptExperimentConfig:
        """Create config from dictionary.

        Args:
            data: Dictionary with config fields

        Returns:
            PromptExperimentConfig instance
        """
        return cls(
            shadow_mode=data.get("shadow_mode", True),
            treatment_percentage=data.get("treatment_percentage", 0.0),
            max_latency_increase_pct=data.get("max_latency_increase_pct", 50.0),
            min_fp_reduction_pct=data.get("min_fp_reduction_pct", 10.0),
            experiment_name=data.get("experiment_name", "nemotron_prompt_v2"),
            started_at=data.get("started_at"),
        )


# Module-level singleton for experiment config
_prompt_experiment_config: PromptExperimentConfig | None = None


def get_prompt_experiment_config() -> PromptExperimentConfig:
    """Get the global prompt experiment configuration singleton.

    Returns:
        PromptExperimentConfig instance with current settings
    """
    global _prompt_experiment_config  # noqa: PLW0603
    if _prompt_experiment_config is None:
        _prompt_experiment_config = PromptExperimentConfig()
    return _prompt_experiment_config


def reset_prompt_experiment_config() -> None:
    """Reset the prompt experiment configuration singleton.

    This is primarily used for testing to ensure clean state between tests.
    """
    global _prompt_experiment_config  # noqa: PLW0603
    _prompt_experiment_config = None
