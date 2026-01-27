"""Prompt evaluator for comparing predictions against expected values.

This module provides utilities for evaluating model predictions against
ground truth expectations from synthetic evaluation samples.

Key Components:
    - EvaluationResult: Result of evaluating a single prediction
    - evaluate_prediction: Evaluate one prediction against expected values
    - calculate_metrics: Calculate aggregate metrics from results
    - evaluate_batch: Evaluate multiple predictions

Example Usage:
    >>> from backend.evaluation.prompt_evaluator import (
    ...     evaluate_prediction,
    ...     calculate_metrics,
    ... )
    >>> from backend.evaluation.prompt_eval_dataset import load_synthetic_eval_dataset
    >>>
    >>> samples = load_synthetic_eval_dataset()
    >>> results = []
    >>> for sample in samples:
    ...     # Get prediction from model (mock here)
    ...     result = evaluate_prediction(sample, actual_score=50, actual_level="medium")
    ...     results.append(result)
    >>> metrics = calculate_metrics(results)
    >>> print(f"Accuracy: {metrics['accuracy']:.2%}")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.evaluation.prompt_eval_dataset import PromptEvalSample


@dataclass
class EvaluationResult:
    """Result from evaluating a single prediction against expected values.

    Attributes:
        scenario_id: Unique identifier for the scenario
        category: Category of the scenario (normal, suspicious, threats)
        actual_score: The predicted risk score (0-100)
        expected_range: Expected risk score range (min, max)
        score_in_range: Whether actual_score is within expected_range
        actual_level: The predicted risk level
        expected_level: The expected risk level
        level_match: Whether actual_level matches expected_level
        deviation: Absolute deviation from the nearest range boundary (0 if in range)
        expected_factors: List of factors that should have been identified
    """

    scenario_id: str
    category: str
    actual_score: int
    expected_range: tuple[int, int]
    score_in_range: bool
    actual_level: str
    expected_level: str
    level_match: bool
    deviation: float = 0.0
    expected_factors: list[str] | None = None

    @property
    def is_accurate(self) -> bool:
        """Check if both score and level are accurate."""
        return self.score_in_range and self.level_match


def evaluate_prediction(
    sample: PromptEvalSample,
    actual_score: int,
    actual_level: str,
) -> EvaluationResult:
    """Evaluate a single prediction against expected values.

    Compares the actual prediction (score and level) against the
    expected values from the sample's ground truth.

    Args:
        sample: The PromptEvalSample containing expected values
        actual_score: The predicted risk score (0-100)
        actual_level: The predicted risk level (low, medium, high, critical)

    Returns:
        EvaluationResult with comparison metrics

    Example:
        >>> sample = PromptEvalSample(
        ...     scenario_id="test_001",
        ...     category="normal",
        ...     media_path=None,
        ...     expected_risk_range=(0, 25),
        ...     expected_risk_level="low",
        ...     expected_factors=[],
        ... )
        >>> result = evaluate_prediction(sample, actual_score=15, actual_level="low")
        >>> assert result.score_in_range is True
        >>> assert result.level_match is True
    """
    min_score, max_score = sample.expected_risk_range

    # Check if score is within expected range
    score_in_range = min_score <= actual_score <= max_score

    # Calculate deviation from range
    if score_in_range:
        deviation = 0.0
    elif actual_score < min_score:
        deviation = float(min_score - actual_score)
    else:
        deviation = float(actual_score - max_score)

    # Normalize level comparison (case-insensitive)
    actual_level_normalized = actual_level.lower().strip()
    expected_level_normalized = sample.expected_risk_level.lower().strip()
    level_match = actual_level_normalized == expected_level_normalized

    return EvaluationResult(
        scenario_id=sample.scenario_id,
        category=sample.category,
        actual_score=actual_score,
        expected_range=sample.expected_risk_range,
        score_in_range=score_in_range,
        actual_level=actual_level,
        expected_level=sample.expected_risk_level,
        level_match=level_match,
        deviation=deviation,
        expected_factors=sample.expected_factors,
    )


def calculate_metrics(results: list[EvaluationResult]) -> dict[str, Any]:
    """Calculate aggregate metrics from evaluation results.

    Computes overall accuracy metrics and breakdowns by category.

    Args:
        results: List of EvaluationResult objects

    Returns:
        Dictionary with aggregate metrics:
        {
            "accuracy": float,  # Fraction of scores within expected range
            "level_accuracy": float,  # Fraction of correct risk levels
            "combined_accuracy": float,  # Fraction where both are correct
            "count": int,  # Total number of results
            "mean_deviation": float,  # Average deviation from range
            "by_category": {  # Metrics broken down by category
                "category_name": {
                    "accuracy": float,
                    "level_accuracy": float,
                    "count": int,
                }
            }
        }

    Example:
        >>> results = [result1, result2, result3]  # EvaluationResults
        >>> metrics = calculate_metrics(results)
        >>> print(f"Overall accuracy: {metrics['accuracy']:.2%}")
    """
    if not results:
        return {
            "accuracy": 0.0,
            "level_accuracy": 0.0,
            "combined_accuracy": 0.0,
            "count": 0,
            "mean_deviation": 0.0,
            "by_category": {},
        }

    # Overall metrics
    total = len(results)
    score_accurate = sum(1 for r in results if r.score_in_range)
    level_accurate = sum(1 for r in results if r.level_match)
    combined_accurate = sum(1 for r in results if r.is_accurate)
    total_deviation = sum(r.deviation for r in results)

    # Group by category
    by_category = _group_metrics_by_category(results)

    return {
        "accuracy": score_accurate / total,
        "level_accuracy": level_accurate / total,
        "combined_accuracy": combined_accurate / total,
        "count": total,
        "mean_deviation": total_deviation / total,
        "by_category": by_category,
    }


def _group_metrics_by_category(results: list[EvaluationResult]) -> dict[str, dict[str, Any]]:
    """Group metrics by category.

    Args:
        results: List of EvaluationResult objects

    Returns:
        Dictionary mapping category names to category metrics
    """
    categories: dict[str, list[EvaluationResult]] = {}
    for r in results:
        if r.category not in categories:
            categories[r.category] = []
        categories[r.category].append(r)

    return {
        cat: {
            "accuracy": sum(1 for r in cat_results if r.score_in_range) / len(cat_results),
            "level_accuracy": sum(1 for r in cat_results if r.level_match) / len(cat_results),
            "combined_accuracy": sum(1 for r in cat_results if r.is_accurate) / len(cat_results),
            "count": len(cat_results),
            "mean_deviation": sum(r.deviation for r in cat_results) / len(cat_results),
        }
        for cat, cat_results in categories.items()
    }


def evaluate_batch(
    samples: list[PromptEvalSample],
    predictions: list[tuple[int, str]],
) -> list[EvaluationResult]:
    """Evaluate a batch of predictions against samples.

    Convenience function for evaluating multiple predictions at once.

    Args:
        samples: List of PromptEvalSample objects
        predictions: List of (score, level) tuples, one per sample

    Returns:
        List of EvaluationResult objects

    Raises:
        ValueError: If samples and predictions have different lengths

    Example:
        >>> samples = load_synthetic_eval_dataset()[:10]
        >>> predictions = [(50, "medium")] * 10  # Mock predictions
        >>> results = evaluate_batch(samples, predictions)
        >>> metrics = calculate_metrics(results)
    """
    if len(samples) != len(predictions):
        raise ValueError(
            f"Number of samples ({len(samples)}) must match "
            f"number of predictions ({len(predictions)})"
        )

    results = []
    for sample, (score, level) in zip(samples, predictions, strict=False):
        result = evaluate_prediction(sample, score, level)
        results.append(result)

    return results


def summarize_results(results: list[EvaluationResult]) -> str:
    """Generate a human-readable summary of evaluation results.

    Args:
        results: List of EvaluationResult objects

    Returns:
        Multi-line string with formatted summary
    """
    if not results:
        return "No evaluation results to summarize."

    metrics = calculate_metrics(results)

    lines = [
        "=" * 50,
        "Evaluation Results Summary",
        "=" * 50,
        f"Total samples evaluated: {metrics['count']}",
        f"Score accuracy (in range): {metrics['accuracy']:.1%}",
        f"Level accuracy: {metrics['level_accuracy']:.1%}",
        f"Combined accuracy: {metrics['combined_accuracy']:.1%}",
        f"Mean deviation: {metrics['mean_deviation']:.2f}",
        "",
        "By Category:",
    ]

    for cat, cat_metrics in sorted(metrics["by_category"].items()):
        lines.append(
            f"  {cat}: {cat_metrics['accuracy']:.1%} score, "
            f"{cat_metrics['level_accuracy']:.1%} level "
            f"({cat_metrics['count']} samples)"
        )

    lines.append("=" * 50)

    return "\n".join(lines)


def get_misclassified(
    results: list[EvaluationResult],
    by_score: bool = True,
    by_level: bool = True,
) -> list[EvaluationResult]:
    """Get results where predictions didn't match expectations.

    Args:
        results: List of EvaluationResult objects
        by_score: Include results where score is out of range
        by_level: Include results where level doesn't match

    Returns:
        Filtered list of misclassified results
    """
    misclassified = []
    for r in results:
        if (by_score and not r.score_in_range) or (
            by_level and not r.level_match and r not in misclassified
        ):
            misclassified.append(r)
    return misclassified
