"""A/B Experiment Runner with Statistical Significance Testing (NEM-3731).

This module provides tools for running prompt A/B experiments and analyzing
results with proper statistical significance testing.

Key Features:
1. **Variant Selection**: Random selection respecting traffic splits
2. **Statistical Analysis**: Two-sample t-tests with effect size calculation
3. **Result Summarization**: Human-readable experiment summaries

Usage:
    from backend.evaluation.ab_experiment_runner import (
        analyze_experiment,
        select_variant,
        summarize_results,
    )
    from backend.config.prompt_ab_config import get_experiment

    # Select variant for a request
    experiment = get_experiment("rubric_vs_current")
    prompt_key = select_variant(experiment)

    # After collecting data, analyze results
    results = analyze_experiment(
        control_scores=[0.82, 0.85, 0.79, 0.88, 0.83],
        variant_scores=[0.91, 0.89, 0.93, 0.87, 0.92],
    )

    # Generate summary
    print(summarize_results(results))
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import numpy as np
from scipy import stats

from backend.config.prompt_ab_config import PromptExperiment


@dataclass
class ExperimentResults:
    """Results of an A/B experiment statistical analysis.

    Contains raw data, descriptive statistics, and statistical test results
    for comparing control and variant performance.

    Attributes:
        control_scores: Raw scores from the control group
        variant_scores: Raw scores from the variant group
        control_mean: Mean of control scores
        variant_mean: Mean of variant scores
        control_std: Standard deviation of control scores
        variant_std: Standard deviation of variant scores
        t_statistic: t-statistic from two-sample t-test
        p_value: p-value from two-sample t-test
        is_significant: Whether p < alpha (default 0.05)
        effect_size: Cohen's d effect size measure

    Effect Size Interpretation (Cohen's d):
        |d| < 0.2: Negligible
        0.2 <= |d| < 0.5: Small
        0.5 <= |d| < 0.8: Medium
        |d| >= 0.8: Large
    """

    control_scores: list[float]
    variant_scores: list[float]
    control_mean: float
    variant_mean: float
    control_std: float
    variant_std: float
    t_statistic: float
    p_value: float
    is_significant: bool
    effect_size: float


def select_variant(experiment: PromptExperiment) -> str:
    """Randomly select control or variant based on traffic split.

    Uses the experiment's traffic_split to probabilistically assign
    requests to either the control or variant group.

    Args:
        experiment: The PromptExperiment configuration

    Returns:
        The prompt key for either control or variant

    Example:
        >>> experiment = PromptExperiment(
        ...     name="test", description="Test",
        ...     control_prompt_key="v1",
        ...     variant_prompt_key="v2",
        ...     traffic_split=0.1  # 10% to variant
        ... )
        >>> prompt_key = select_variant(experiment)
        >>> # 90% chance of "v1", 10% chance of "v2"
    """
    # nosemgrep: insecure-random - A/B traffic split doesn't need crypto-secure RNG
    if random.random() < experiment.traffic_split:  # noqa: S311
        return experiment.variant_prompt_key
    return experiment.control_prompt_key


def analyze_experiment(
    control_scores: list[float],
    variant_scores: list[float],
    alpha: float = 0.05,
) -> ExperimentResults:
    """Analyze A/B experiment results for statistical significance.

    Performs a two-sample independent t-test to determine if there is
    a statistically significant difference between control and variant
    performance. Also calculates Cohen's d effect size.

    Args:
        control_scores: Performance scores from the control group
        variant_scores: Performance scores from the variant group
        alpha: Significance level for hypothesis testing (default 0.05)

    Returns:
        ExperimentResults with statistical analysis

    Raises:
        ValueError: If either list has fewer than 2 scores

    Example:
        >>> results = analyze_experiment(
        ...     control_scores=[0.80, 0.82, 0.79, 0.81, 0.83],
        ...     variant_scores=[0.88, 0.90, 0.87, 0.89, 0.91],
        ...     alpha=0.05
        ... )
        >>> if results.is_significant:
        ...     print(f"Variant is significantly better! (p={results.p_value:.4f})")
    """
    if len(control_scores) < 2:
        raise ValueError("control_scores must have at least 2 values")
    if len(variant_scores) < 2:
        raise ValueError("variant_scores must have at least 2 values")

    control_arr = np.array(control_scores)
    variant_arr = np.array(variant_scores)

    # Descriptive statistics
    control_mean = float(np.mean(control_arr))
    variant_mean = float(np.mean(variant_arr))
    control_std = float(np.std(control_arr, ddof=1))
    variant_std = float(np.std(variant_arr, ddof=1))

    # Two-sample independent t-test
    t_stat, p_value = stats.ttest_ind(control_arr, variant_arr)

    # Cohen's d effect size
    # Using pooled standard deviation
    n_control = len(control_arr)
    n_variant = len(variant_arr)
    pooled_std = np.sqrt(
        ((n_control - 1) * control_std**2 + (n_variant - 1) * variant_std**2)
        / (n_control + n_variant - 2)
    )
    effect_size = (variant_mean - control_mean) / pooled_std if pooled_std > 0 else 0.0

    return ExperimentResults(
        control_scores=control_scores,
        variant_scores=variant_scores,
        control_mean=control_mean,
        variant_mean=variant_mean,
        control_std=control_std,
        variant_std=variant_std,
        t_statistic=float(t_stat),
        p_value=float(p_value),
        is_significant=bool(p_value < alpha),  # Convert numpy bool to Python bool
        effect_size=float(effect_size),
    )


def _interpret_effect_size(effect_size: float) -> str:
    """Interpret Cohen's d effect size.

    Args:
        effect_size: Cohen's d value

    Returns:
        Human-readable interpretation
    """
    abs_d = abs(effect_size)
    if abs_d < 0.2:
        return "negligible"
    elif abs_d < 0.5:
        return "small"
    elif abs_d < 0.8:
        return "medium"
    else:
        return "large"


def summarize_results(results: ExperimentResults) -> str:
    """Generate human-readable summary of experiment results.

    Creates a formatted report with:
    - Significance determination
    - Descriptive statistics for both groups
    - Statistical test results
    - Effect size interpretation

    Args:
        results: ExperimentResults from analyze_experiment()

    Returns:
        Formatted string summary

    Example:
        >>> results = analyze_experiment(control, variant)
        >>> print(summarize_results(results))
        A/B Experiment Results (SIGNIFICANT)
        =====================================
        Control: mean=0.81, std=0.02, n=100
        Variant: mean=0.89, std=0.02, n=100
        ...
    """
    sig_text = "SIGNIFICANT" if results.is_significant else "NOT SIGNIFICANT"
    effect_interpretation = _interpret_effect_size(results.effect_size)

    # Determine if variant is better or worse
    if results.variant_mean > results.control_mean:
        direction = "Variant performs BETTER than control"
    elif results.variant_mean < results.control_mean:
        direction = "Variant performs WORSE than control"
    else:
        direction = "No difference between variant and control"

    return f"""
A/B Experiment Results ({sig_text})
=====================================
Control: mean={results.control_mean:.4f}, std={results.control_std:.4f}, n={len(results.control_scores)}
Variant: mean={results.variant_mean:.4f}, std={results.variant_std:.4f}, n={len(results.variant_scores)}

Statistical Analysis:
- t-statistic: {results.t_statistic:.4f}
- p-value: {results.p_value:.4f}
- Effect size (Cohen's d): {results.effect_size:.4f} ({effect_interpretation})
- Significant at alpha=0.05: {results.is_significant}

Interpretation:
- {direction}
- {"The difference IS statistically significant" if results.is_significant else "The difference is NOT statistically significant"}
"""


# =============================================================================
# Module-level Exports
# =============================================================================

__all__ = [
    "ExperimentResults",
    "analyze_experiment",
    "select_variant",
    "summarize_results",
]
