"""Metrics calculation for prompt evaluation.

This module provides functions for calculating evaluation metrics including:
- Risk score deviation from ground truth ranges
- Reasoning similarity using word overlap (MVP) or embeddings
- Key point coverage in generated reasoning
- Aggregated metrics across templates and scenario types

Metrics follow the design in docs/plans/2026-01-21-nemo-data-designer-integration-design.md
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import pandas as pd


def calculate_risk_deviation(
    actual: int,
    expected_range: tuple[int, int],
) -> float:
    """Calculate deviation of actual risk score from expected range.

    Returns 0 if the actual score is within the expected range, otherwise
    returns the positive distance to the nearest boundary.

    Args:
        actual: The actual risk score (0-100)
        expected_range: Tuple of (min_score, max_score) representing the
            acceptable range for the scenario type

    Returns:
        Deviation from range. 0.0 if within range, positive distance otherwise.

    Examples:
        >>> calculate_risk_deviation(50, (40, 60))  # Within range
        0.0
        >>> calculate_risk_deviation(30, (40, 60))  # Below range
        10.0
        >>> calculate_risk_deviation(80, (40, 60))  # Above range
        20.0
    """
    min_score, max_score = expected_range

    if min_score <= actual <= max_score:
        return 0.0

    if actual < min_score:
        return float(min_score - actual)

    return float(actual - max_score)


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase words.

    Removes punctuation and splits on whitespace. Used for simple
    word-overlap similarity calculation.

    Args:
        text: Text to tokenize

    Returns:
        List of lowercase word tokens
    """
    # Remove punctuation and convert to lowercase
    text = re.sub(r"[^\w\s]", "", text.lower())
    return text.split()


def calculate_reasoning_similarity(
    actual: str,
    expected: str,
) -> float:
    """Calculate similarity between actual and expected reasoning.

    Uses simple word overlap (Jaccard similarity) as MVP implementation.
    Future versions may use cosine similarity with sentence embeddings.

    Args:
        actual: The generated reasoning text
        expected: The expected/ground truth reasoning text

    Returns:
        Similarity score between 0.0 (no overlap) and 1.0 (identical)

    Examples:
        >>> calculate_reasoning_similarity("unknown person at door", "unknown person at front door")
        0.8  # 4 shared words out of 5 unique words
    """
    if not actual or not expected:
        return 0.0

    actual_tokens = set(_tokenize(actual))
    expected_tokens = set(_tokenize(expected))

    if not actual_tokens or not expected_tokens:
        return 0.0

    # Jaccard similarity: intersection / union
    intersection = len(actual_tokens & expected_tokens)
    union = len(actual_tokens | expected_tokens)

    return intersection / union if union > 0 else 0.0


def calculate_key_point_coverage(
    reasoning: str,
    key_points: list[str],
) -> float:
    """Calculate fraction of key points mentioned in reasoning.

    Performs case-insensitive substring matching to determine how many
    of the expected key points appear in the generated reasoning.

    Args:
        reasoning: The generated reasoning text
        key_points: List of key points that should be mentioned

    Returns:
        Coverage score between 0.0 (no points covered) and 1.0 (all covered)

    Examples:
        >>> reasoning = "Unknown person detected at night near the front door"
        >>> key_points = ["unknown person", "night", "entry point"]
        >>> calculate_key_point_coverage(reasoning, key_points)
        0.666...  # 2 of 3 key points found
    """
    if not key_points:
        return 1.0  # No points to cover means full coverage

    if not reasoning:
        return 0.0

    reasoning_lower = reasoning.lower()
    covered = sum(1 for point in key_points if point.lower() in reasoning_lower)

    return covered / len(key_points)


def aggregate_metrics(
    results: pd.DataFrame,
    group_by: list[str] | None = None,  # noqa: ARG001 - reserved for custom grouping in future
) -> dict:
    """Aggregate evaluation metrics across scenarios.

    Computes summary statistics (mean, std, percentiles) for key metrics,
    optionally grouped by template, scenario_type, or enrichment_level.

    Args:
        results: DataFrame with evaluation results containing columns:
            - template_name: Name of the prompt template
            - scenario_type: Type of scenario (normal, suspicious, threat, edge_case)
            - enrichment_level: Level of enrichment (none, basic, full)
            - risk_deviation: Deviation from ground truth risk range
            - key_point_coverage: Fraction of key points covered
            - reasoning_similarity: Similarity to expected reasoning
            - risk_score: The actual risk score generated
        group_by: Optional list of columns to group by. Defaults to
            ["template_name", "scenario_type", "enrichment_level"]

    Returns:
        Dictionary with aggregated metrics structure:
        {
            "overall": {
                "total_scenarios": int,
                "mean_risk_deviation": float,
                "mean_key_point_coverage": float,
                "mean_reasoning_similarity": float,
                "within_range_pct": float,  # % of scenarios with deviation=0
            },
            "by_template": {
                "template_name": {
                    "mean_risk_deviation": float,
                    ...
                }
            },
            "by_scenario_type": {...},
            "by_enrichment_level": {...},
            "percentiles": {
                "risk_deviation": {"p50": float, "p90": float, "p99": float},
                "key_point_coverage": {...},
                "reasoning_similarity": {...}
            }
        }
    """

    if results.empty:
        return {
            "overall": {
                "total_scenarios": 0,
                "mean_risk_deviation": 0.0,
                "mean_key_point_coverage": 0.0,
                "mean_reasoning_similarity": 0.0,
                "within_range_pct": 0.0,
            },
            "by_template": {},
            "by_scenario_type": {},
            "by_enrichment_level": {},
            "percentiles": {},
        }

    # Overall metrics
    overall = {
        "total_scenarios": len(results),
        "mean_risk_deviation": float(results["risk_deviation"].mean()),
        "std_risk_deviation": float(results["risk_deviation"].std()),
        "mean_key_point_coverage": float(results["key_point_coverage"].mean()),
        "std_key_point_coverage": float(results["key_point_coverage"].std()),
        "mean_reasoning_similarity": float(results["reasoning_similarity"].mean()),
        "std_reasoning_similarity": float(results["reasoning_similarity"].std()),
        "within_range_pct": float((results["risk_deviation"] == 0).mean() * 100),
    }

    # Per-template metrics
    by_template = {}
    if "template_name" in results.columns:
        for template, group in results.groupby("template_name"):
            by_template[str(template)] = {
                "count": len(group),
                "mean_risk_deviation": float(group["risk_deviation"].mean()),
                "std_risk_deviation": float(group["risk_deviation"].std()),
                "mean_key_point_coverage": float(group["key_point_coverage"].mean()),
                "mean_reasoning_similarity": float(group["reasoning_similarity"].mean()),
                "within_range_pct": float((group["risk_deviation"] == 0).mean() * 100),
            }

    # Per-scenario-type metrics
    by_scenario_type = {}
    if "scenario_type" in results.columns:
        for scenario_type, group in results.groupby("scenario_type"):
            by_scenario_type[str(scenario_type)] = {
                "count": len(group),
                "mean_risk_deviation": float(group["risk_deviation"].mean()),
                "std_risk_deviation": float(group["risk_deviation"].std()),
                "mean_key_point_coverage": float(group["key_point_coverage"].mean()),
                "mean_reasoning_similarity": float(group["reasoning_similarity"].mean()),
                "within_range_pct": float((group["risk_deviation"] == 0).mean() * 100),
            }

    # Per-enrichment-level metrics
    by_enrichment_level = {}
    if "enrichment_level" in results.columns:
        for level, group in results.groupby("enrichment_level"):
            by_enrichment_level[str(level)] = {
                "count": len(group),
                "mean_risk_deviation": float(group["risk_deviation"].mean()),
                "std_risk_deviation": float(group["risk_deviation"].std()),
                "mean_key_point_coverage": float(group["key_point_coverage"].mean()),
                "mean_reasoning_similarity": float(group["reasoning_similarity"].mean()),
                "within_range_pct": float((group["risk_deviation"] == 0).mean() * 100),
            }

    # Percentiles for key metrics
    percentiles = {}
    for metric in ["risk_deviation", "key_point_coverage", "reasoning_similarity"]:
        if metric in results.columns:
            values = results[metric].dropna()
            if len(values) > 0:
                percentiles[metric] = {
                    "p50": float(np.percentile(values, 50)),
                    "p90": float(np.percentile(values, 90)),
                    "p99": float(np.percentile(values, 99)),
                    "min": float(values.min()),
                    "max": float(values.max()),
                }

    return {
        "overall": overall,
        "by_template": by_template,
        "by_scenario_type": by_scenario_type,
        "by_enrichment_level": by_enrichment_level,
        "percentiles": percentiles,
    }


def rank_templates(metrics: dict) -> list[dict]:
    """Rank templates by overall performance.

    Creates a ranked list of templates based on a composite score that
    considers risk deviation (lower is better), key point coverage (higher
    is better), and reasoning similarity (higher is better).

    Args:
        metrics: Aggregated metrics dictionary from aggregate_metrics()

    Returns:
        List of template rankings, sorted best to worst:
        [
            {
                "rank": 1,
                "template_name": str,
                "composite_score": float,
                "mean_risk_deviation": float,
                "mean_key_point_coverage": float,
                "mean_reasoning_similarity": float,
                "within_range_pct": float,
            },
            ...
        ]
    """
    by_template = metrics.get("by_template", {})

    if not by_template:
        return []

    rankings = []
    for template_name, template_metrics in by_template.items():
        # Composite score: prioritize low deviation and high coverage
        # Deviation is inverted (lower is better -> higher score)
        # Normalize deviation to 0-1 range assuming max deviation of 100
        deviation_score = 1.0 - min(template_metrics["mean_risk_deviation"] / 100, 1.0)
        coverage_score = template_metrics["mean_key_point_coverage"]
        similarity_score = template_metrics["mean_reasoning_similarity"]

        # Weighted composite (deviation most important, then coverage, then similarity)
        composite = 0.5 * deviation_score + 0.3 * coverage_score + 0.2 * similarity_score

        rankings.append(
            {
                "template_name": template_name,
                "composite_score": composite,
                "mean_risk_deviation": template_metrics["mean_risk_deviation"],
                "mean_key_point_coverage": template_metrics["mean_key_point_coverage"],
                "mean_reasoning_similarity": template_metrics["mean_reasoning_similarity"],
                "within_range_pct": template_metrics["within_range_pct"],
                "count": template_metrics["count"],
            }
        )

    # Sort by composite score (descending - higher is better)
    rankings.sort(key=lambda x: x["composite_score"], reverse=True)

    # Add rank
    for i, ranking in enumerate(rankings, 1):
        ranking["rank"] = i

    return rankings
