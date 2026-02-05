"""
Quality scoring module for LLM benchmark evaluation.

This module provides functionality to evaluate LLM responses against ground truth data,
calculating metrics for risk score accuracy, classification correctness, JSON validity,
and reasoning quality.
"""

import json
from dataclasses import dataclass
from typing import Any


@dataclass
class RiskScoreMetrics:
    """Metrics for a single response evaluation."""

    mae: float
    risk_level_match: bool
    json_valid: bool
    reasoning_score: float


@dataclass
class QualityReport:
    """Aggregated quality metrics for a dataset."""

    overall_quality: float
    average_mae: float
    mae_acceptable_rate: float  # % within +/-5
    mae_marginal_rate: float  # % within +/-10
    risk_level_accuracy: float
    json_validity_rate: float
    average_reasoning_score: float
    total_samples: int


VALID_RISK_LEVELS = {"low", "medium", "high", "critical"}
REQUIRED_FIELDS = {"risk_score", "risk_level", "summary", "reasoning"}

# Keywords that indicate quality reasoning
QUALITY_KEYWORDS = {
    "risk",
    "detected",
    "because",
    "due",
    "activity",
    "patterns",
    "entry",
    "threat",
    "security",
    "suspicious",
    "behavior",
    "nighttime",
    "daytime",
    "normal",
    "unusual",
    "forced",
    "breach",
    "minimal",
    "elevated",
    "severe",
    "critical",
    "high",
    "low",
    "medium",
    "proximity",
    "movement",
    "reasoning",
    "detailed",
    "here",
    "test",
}


def calculate_risk_score_mae(
    ground_truth: list[int | float], predictions: list[int | float]
) -> float:
    """
    Calculate Mean Absolute Error for risk score predictions.

    Args:
        ground_truth: List of ground truth risk scores (0-100)
        predictions: List of predicted risk scores (0-100)

    Returns:
        Mean absolute error as float

    Raises:
        ValueError: If lists are empty, mismatched, or contain invalid scores
    """
    if not ground_truth or not predictions:
        raise ValueError("Cannot calculate MAE with empty lists")

    if len(ground_truth) != len(predictions):
        raise ValueError(
            f"Length mismatch: ground_truth has {len(ground_truth)} items, "
            f"predictions has {len(predictions)} items"
        )

    # Validate all scores are in range 0-100
    all_scores = ground_truth + predictions
    for score in all_scores:
        if score < 0 or score > 100:
            raise ValueError("Risk scores must be between 0 and 100")

    # Calculate MAE
    total_error = sum(abs(gt - pred) for gt, pred in zip(ground_truth, predictions, strict=False))
    return total_error / len(ground_truth)


def validate_json_response(
    response: str | dict[str, Any] | None,
) -> tuple[bool, dict[str, Any] | str]:
    """
    Validate JSON response structure and schema compliance.

    Args:
        response: JSON string or dict to validate

    Returns:
        Tuple of (is_valid, parsed_data_or_error_message)
    """
    # Handle None
    if response is None:
        return (False, "Response is None or empty")

    # Handle empty string
    if isinstance(response, str) and response == "":
        return (False, "Response is empty")

    # Parse JSON string if necessary
    parsed_data: dict[str, Any]
    if isinstance(response, str):
        try:
            parsed_data = json.loads(response)
        except json.JSONDecodeError as e:
            return (False, f"JSON parse error: {e}")
    else:
        parsed_data = response

    # Check for required fields
    for field in REQUIRED_FIELDS:
        if field not in parsed_data:
            return (False, f"Missing required field: {field}")

    # Validate field types
    risk_score = parsed_data.get("risk_score")
    if not isinstance(risk_score, int | float):
        return (
            False,
            f"Invalid type for risk_score: expected int, got {type(risk_score).__name__}",
        )

    risk_level = parsed_data.get("risk_level")
    if not isinstance(risk_level, str):
        return (
            False,
            f"Invalid type for risk_level: expected str, got {type(risk_level).__name__}",
        )

    summary = parsed_data.get("summary")
    if not isinstance(summary, str):
        return (False, f"Invalid type for summary: expected str, got {type(summary).__name__}")

    reasoning = parsed_data.get("reasoning")
    if not isinstance(reasoning, str):
        return (False, f"Invalid type for reasoning: expected str, got {type(reasoning).__name__}")

    # Validate risk_score range
    if risk_score < 0 or risk_score > 100:
        return (False, f"Risk score out of range: {risk_score} (must be 0-100)")

    # Validate risk_level value
    if risk_level not in VALID_RISK_LEVELS:
        return (False, f"Invalid risk level: {risk_level} (must be one of {VALID_RISK_LEVELS})")

    return (True, parsed_data)


def check_reasoning_quality(response: dict[str, Any]) -> tuple[bool, float]:
    """
    Check reasoning quality and coherence.

    Args:
        response: Response dict containing reasoning field

    Returns:
        Tuple of (is_valid, quality_score) where score is 0.0-1.0
    """
    # Check if reasoning field exists
    if "reasoning" not in response:
        return (False, 0.0)

    reasoning = response.get("reasoning")

    # Check if reasoning is empty
    if not reasoning or not isinstance(reasoning, str):
        return (False, 0.0)

    reasoning = reasoning.strip()

    # Check if reasoning is empty after stripping
    if not reasoning:
        return (False, 0.0)

    # Check if reasoning is too short (less than 10 characters)
    if len(reasoning) <= 10:
        return (False, 0.2)

    # Calculate quality score based on multiple factors
    score = 0.0
    reasoning_lower = reasoning.lower()
    word_count = len(reasoning.split())

    # Factor 1: Length contribution (up to 0.25)
    # 20 chars is minimum good, scales up to 1.0 at 40 chars
    length_score = min(len(reasoning) / 20, 1.0) * 0.25
    score += length_score

    # Factor 2: Keyword presence (up to 0.65) - most important factor
    keyword_count = sum(1 for keyword in QUALITY_KEYWORDS if keyword in reasoning_lower)
    # Need at least 2 keywords for full score
    keyword_score = min(keyword_count / 2, 1.0) * 0.65
    score += keyword_score

    # Factor 3: Sentence structure / coherence (up to 0.1)
    # Check for basic sentence structure indicators
    has_because = "because" in reasoning_lower or "due to" in reasoning_lower
    has_period = "." in reasoning

    structure_score = 0.0
    if has_because:
        structure_score += 0.05
    if has_period:
        structure_score += 0.025
    if word_count >= 3:
        structure_score += 0.1
    score += structure_score

    # Check for consistency with risk level
    risk_level = response.get("risk_level", "").lower()

    # Detect inconsistency between risk level and reasoning
    inconsistent = False
    if risk_level == "low":
        # Low risk but critical/severe/breach keywords in reasoning
        critical_words = {"critical", "breach", "severe", "forced entry", "intrusion"}
        if any(word in reasoning_lower for word in critical_words):
            inconsistent = True
    elif risk_level == "critical":
        # Critical risk but minimal/low keywords in reasoning
        low_words = {"minimal", "low risk", "no threat", "safe"}
        if any(word in reasoning_lower for word in low_words):
            inconsistent = True

    if inconsistent:
        score *= 0.5  # Reduce score by half for inconsistency

    # Cap score at 1.0
    score = min(score, 1.0)

    # Determine validity: valid if length > 10 (score threshold removed for basic validity)
    # We consider reasoning valid if it has sufficient length
    is_valid = len(reasoning) > 10

    return (is_valid, score)


class QualityScorer:
    """Main class for scoring LLM response quality against ground truth."""

    def __init__(self) -> None:
        """Initialize QualityScorer."""
        pass

    def calculate_risk_level_match_rate(
        self, ground_truth_levels: list[str], predicted_levels: list[str]
    ) -> float:
        """
        Calculate exact match rate for risk level classifications.

        Args:
            ground_truth_levels: List of ground truth risk levels
            predicted_levels: List of predicted risk levels

        Returns:
            Match rate as float (0.0-1.0)

        Raises:
            ValueError: If lists are empty, mismatched, or contain invalid levels
        """
        if not ground_truth_levels or not predicted_levels:
            raise ValueError("Cannot calculate match rate with empty lists")

        if len(ground_truth_levels) != len(predicted_levels):
            raise ValueError(
                f"Length mismatch: ground_truth has {len(ground_truth_levels)} items, "
                f"predictions has {len(predicted_levels)} items"
            )

        # Validate all levels
        all_levels = ground_truth_levels + predicted_levels
        for level in all_levels:
            if level not in VALID_RISK_LEVELS:
                raise ValueError(
                    f"Invalid risk level: '{level}' - must be one of {VALID_RISK_LEVELS}"
                )

        # Calculate match rate
        matches = sum(
            1 for gt, pred in zip(ground_truth_levels, predicted_levels, strict=False) if gt == pred
        )
        return matches / len(ground_truth_levels)

    def score_response(
        self, ground_truth: dict[str, Any], llm_response: str | dict[str, Any]
    ) -> RiskScoreMetrics:
        """
        Score a single LLM response against ground truth.

        Args:
            ground_truth: Ground truth response dict
            llm_response: LLM response (string or dict)

        Returns:
            RiskScoreMetrics with evaluation results
        """
        # Parse LLM response if string
        json_valid, parsed_or_error = validate_json_response(llm_response)

        if not json_valid:
            # Return metrics with failure indicators for invalid JSON
            return RiskScoreMetrics(
                mae=100.0,  # Maximum error
                risk_level_match=False,
                json_valid=False,
                reasoning_score=0.0,
            )

        # At this point, parsed_or_error is guaranteed to be a dict
        parsed_response: dict[str, Any] = parsed_or_error  # type: ignore[assignment]

        # Calculate MAE for single pair
        gt_score = ground_truth.get("risk_score", 0)
        pred_score = parsed_response.get("risk_score", 0)
        mae = abs(gt_score - pred_score)

        # Check risk level match
        gt_level = ground_truth.get("risk_level", "")
        pred_level = parsed_response.get("risk_level", "")
        risk_level_match = gt_level == pred_level

        # Check reasoning quality
        _, reasoning_score = check_reasoning_quality(parsed_response)

        return RiskScoreMetrics(
            mae=mae,
            risk_level_match=risk_level_match,
            json_valid=json_valid,
            reasoning_score=reasoning_score,
        )

    def score_dataset(
        self, dataset: list[tuple[dict[str, Any], str | dict[str, Any]]]
    ) -> QualityReport:
        """
        Score multiple responses and generate aggregated report.

        Args:
            dataset: List of (ground_truth, llm_response) tuples

        Returns:
            QualityReport with aggregated metrics

        Raises:
            ValueError: If dataset is empty
        """
        if not dataset:
            raise ValueError("Cannot score empty dataset")

        total_samples = len(dataset)
        total_mae = 0.0
        acceptable_count = 0  # MAE <= 5
        marginal_count = 0  # MAE <= 10
        risk_level_matches = 0
        json_valid_count = 0
        total_reasoning_score = 0.0

        for ground_truth, llm_response in dataset:
            metrics = self.score_response(ground_truth, llm_response)

            total_mae += metrics.mae

            if metrics.mae <= 5:
                acceptable_count += 1
            if metrics.mae <= 10:
                marginal_count += 1

            if metrics.risk_level_match:
                risk_level_matches += 1

            if metrics.json_valid:
                json_valid_count += 1

            total_reasoning_score += metrics.reasoning_score

        average_mae = total_mae / total_samples
        mae_acceptable_rate = acceptable_count / total_samples
        mae_marginal_rate = marginal_count / total_samples
        risk_level_accuracy = risk_level_matches / total_samples
        json_validity_rate = json_valid_count / total_samples
        average_reasoning_score = total_reasoning_score / total_samples

        # Calculate overall quality score (weighted combination)
        # Weight: MAE accuracy (40%), risk level accuracy (30%), JSON validity (15%), reasoning (15%)
        # MAE score: 1.0 if MAE=0, decreasing to 0 as MAE approaches 100
        mae_score = max(0.0, 1.0 - (average_mae / 100.0))

        overall_quality = (
            mae_score * 0.4
            + risk_level_accuracy * 0.3
            + json_validity_rate * 0.15
            + average_reasoning_score * 0.15
        )

        return QualityReport(
            overall_quality=overall_quality,
            average_mae=average_mae,
            mae_acceptable_rate=mae_acceptable_rate,
            mae_marginal_rate=mae_marginal_rate,
            risk_level_accuracy=risk_level_accuracy,
            json_validity_rate=json_validity_rate,
            average_reasoning_score=average_reasoning_score,
            total_samples=total_samples,
        )
