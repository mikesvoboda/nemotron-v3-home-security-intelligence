"""Prompt A/B Testing Configuration for Experiment Management (NEM-3731).

This module provides configuration for prompt A/B experiments with support for
multiple predefined experiments and statistical analysis integration.

Key Features:
1. **Experiment Configuration**: Define control and variant prompts with traffic splits
2. **Metrics Definition**: Configurable metrics for experiment evaluation
3. **Dataset Integration**: Connect experiments to evaluation datasets

Usage:
    from backend.config.prompt_ab_config import (
        PromptExperiment,
        EXPERIMENTS,
        get_experiment,
    )

    # Get a predefined experiment
    experiment = get_experiment("rubric_vs_current")
    if experiment:
        print(f"Testing {experiment.control_prompt_key} vs {experiment.variant_prompt_key}")
        print(f"Traffic split: {experiment.traffic_split:.0%} to variant")

    # Create a custom experiment
    custom = PromptExperiment(
        name="custom_test",
        description="Custom prompt comparison",
        control_prompt_key="baseline",
        variant_prompt_key="experimental",
        traffic_split=0.2,  # 20% to variant
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PromptExperiment:
    """Configuration for a prompt A/B experiment.

    Defines the parameters for comparing two prompt versions with statistical
    analysis support.

    Attributes:
        name: Unique identifier for the experiment
        description: Human-readable description of what's being tested
        control_prompt_key: Key to identify the control (baseline) prompt
        variant_prompt_key: Key to identify the variant (experimental) prompt
        traffic_split: Fraction of traffic sent to variant (0.0-1.0). Default 0.1 (10%)
        eval_dataset_path: Path to evaluation dataset with ground truth
        metrics: List of metric names to track for the experiment
        enabled: Whether the experiment is active

    Example:
        # Standard 10% experiment
        experiment = PromptExperiment(
            name="reasoning_test",
            description="Test chain-of-thought reasoning",
            control_prompt_key="calibrated_system",
            variant_prompt_key="reasoning_enabled",
        )

        # Higher traffic experiment
        experiment = PromptExperiment(
            name="full_test",
            description="Full 50/50 A/B test",
            control_prompt_key="v1",
            variant_prompt_key="v2",
            traffic_split=0.5,
        )
    """

    name: str
    description: str
    control_prompt_key: str
    variant_prompt_key: str
    traffic_split: float = 0.1
    eval_dataset_path: Path = field(default_factory=lambda: Path("data/synthetic"))
    metrics: list[str] = field(
        default_factory=lambda: [
            "json_parse_success_rate",
            "score_in_range_accuracy",
            "level_match_accuracy",
            "response_latency_ms",
        ]
    )
    enabled: bool = True

    def __post_init__(self) -> None:
        """Validate experiment configuration after initialization."""
        if not self.name:
            raise ValueError("Experiment name cannot be empty")
        if not self.description:
            raise ValueError("Experiment description cannot be empty")
        if not self.control_prompt_key:
            raise ValueError("Control prompt key cannot be empty")
        if not self.variant_prompt_key:
            raise ValueError("Variant prompt key cannot be empty")
        if self.control_prompt_key == self.variant_prompt_key:
            raise ValueError("Control and variant prompt keys must be different")
        if not 0.0 <= self.traffic_split <= 1.0:
            raise ValueError(f"traffic_split must be between 0.0 and 1.0, got {self.traffic_split}")


# =============================================================================
# Predefined Experiments
# =============================================================================

EXPERIMENTS: dict[str, PromptExperiment] = {
    "rubric_vs_current": PromptExperiment(
        name="rubric_vs_current",
        description="Compare rubric-based scoring against current prompt",
        control_prompt_key="calibrated_system",
        variant_prompt_key="rubric_enhanced",
    ),
    "cot_vs_current": PromptExperiment(
        name="cot_vs_current",
        description="Compare chain-of-thought reasoning against current prompt",
        control_prompt_key="calibrated_system",
        variant_prompt_key="reasoning_enabled",
    ),
}


def get_experiment(name: str) -> PromptExperiment | None:
    """Get experiment configuration by name.

    Args:
        name: The name of the experiment to retrieve

    Returns:
        PromptExperiment if found, None otherwise

    Example:
        >>> experiment = get_experiment("rubric_vs_current")
        >>> if experiment:
        ...     print(f"Found experiment: {experiment.description}")
    """
    return EXPERIMENTS.get(name)


def list_experiments() -> list[str]:
    """List all available experiment names.

    Returns:
        List of experiment names

    Example:
        >>> names = list_experiments()
        >>> print(f"Available experiments: {names}")
    """
    return list(EXPERIMENTS.keys())


def get_enabled_experiments() -> list[PromptExperiment]:
    """Get all enabled experiments.

    Returns:
        List of enabled PromptExperiment configurations

    Example:
        >>> enabled = get_enabled_experiments()
        >>> for exp in enabled:
        ...     print(f"{exp.name}: {exp.traffic_split:.0%} to variant")
    """
    return [exp for exp in EXPERIMENTS.values() if exp.enabled]


# =============================================================================
# Module-level Exports
# =============================================================================

__all__ = [
    "EXPERIMENTS",
    "PromptExperiment",
    "get_enabled_experiments",
    "get_experiment",
    "list_experiments",
]
