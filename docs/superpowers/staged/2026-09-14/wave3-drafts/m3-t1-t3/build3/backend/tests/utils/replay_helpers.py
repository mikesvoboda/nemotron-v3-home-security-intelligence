"""Utilities for historical event replay testing.

This module provides reusable utilities for testing the prompt replay infrastructure,
including data classes, statistics calculation, and distribution validation.

Part of NEM-3339: Historical Event Replay Testing (Phase 7.3 of NEM-3008).

Usage:
    from backend.tests.utils.replay_helpers import (
        ReplayResult,
        ReplayStatistics,
        DistributionTargets,
        classify_risk_level,
        calculate_replay_statistics,
        validate_distribution,
        generate_replay_report,
    )

    # Create replay results
    result = ReplayResult(
        event_id=1,
        camera_id="cam1",
        original_risk_score=70,
        new_risk_score=35,
        ...
    )

    # Calculate statistics
    stats = calculate_replay_statistics([result, ...])

    # Validate distribution
    is_valid, messages = validate_distribution(stats)
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any


@dataclass
class ReplayResult:
    """Result from replaying a single event through the new prompt pipeline.

    Attributes:
        event_id: Database ID of the original event
        camera_id: Camera that captured the event
        original_risk_score: Risk score from original analysis (None if not available)
        original_risk_level: Risk level from original analysis
        new_risk_score: Risk score from replay with new prompt
        new_risk_level: Risk level from replay
        score_diff: Absolute difference between original and new scores
        detection_count: Number of detections in the event
        object_types: Comma-separated object types detected
    """

    event_id: int
    camera_id: str
    original_risk_score: int | None
    original_risk_level: str | None
    new_risk_score: int
    new_risk_level: str
    score_diff: int
    detection_count: int
    object_types: str | None

    @property
    def score_decreased(self) -> bool:
        """Check if the new score is lower than the original."""
        if self.original_risk_score is None:
            return False
        return self.new_risk_score < self.original_risk_score

    @property
    def score_increased(self) -> bool:
        """Check if the new score is higher than the original."""
        if self.original_risk_score is None:
            return False
        return self.new_risk_score > self.original_risk_score

    @property
    def level_changed(self) -> bool:
        """Check if the risk level changed between original and new."""
        if self.original_risk_level is None:
            return False
        return self.original_risk_level != self.new_risk_level

    @property
    def is_downgrade(self) -> bool:
        """Check if the event was downgraded (high/critical -> medium/low)."""
        high_levels = {"high", "critical"}
        low_levels = {"low", "medium"}
        return self.original_risk_level in high_levels and self.new_risk_level in low_levels

    @property
    def is_upgrade(self) -> bool:
        """Check if the event was upgraded (low/medium -> high/critical)."""
        low_levels = {"low", "medium"}
        high_levels = {"high", "critical"}
        return self.original_risk_level in low_levels and self.new_risk_level in high_levels


@dataclass
class ReplayStatistics:
    """Aggregated statistics from replaying multiple events.

    Attributes:
        total_events: Total number of events replayed
        low_count: Number of events scoring LOW (< 40)
        medium_count: Number of events scoring MEDIUM (40-69)
        high_count: Number of events scoring HIGH (>= 70)
        mean_score: Mean of all new scores
        median_score: Median of all new scores
        std_dev: Standard deviation of new scores
        mean_score_diff: Mean of score differences
        scores_decreased_count: Count of events where score decreased
        scores_increased_count: Count of events where score increased
        scores_unchanged_count: Count of events where score stayed same
    """

    total_events: int
    low_count: int
    medium_count: int
    high_count: int
    mean_score: float
    median_score: float
    std_dev: float
    mean_score_diff: float
    scores_decreased_count: int
    scores_increased_count: int
    scores_unchanged_count: int

    @property
    def low_percentage(self) -> float:
        """Percentage of events scoring LOW."""
        return (self.low_count / self.total_events * 100) if self.total_events > 0 else 0

    @property
    def medium_percentage(self) -> float:
        """Percentage of events scoring MEDIUM."""
        return (self.medium_count / self.total_events * 100) if self.total_events > 0 else 0

    @property
    def high_percentage(self) -> float:
        """Percentage of events scoring HIGH."""
        return (self.high_count / self.total_events * 100) if self.total_events > 0 else 0

    @property
    def critical_count(self) -> int:
        """Count of events scoring CRITICAL (>= 90) - subset of high_count."""
        # Note: This requires the original results to calculate accurately
        # For now, return 0 as high_count includes both high and critical
        return 0


@dataclass
class DistributionTargets:
    """Target distribution ranges for prompt calibration.

    These targets represent the expected distribution after prompt improvements:
    - LOW: 50-60% of events (benign activity like pets, deliveries)
    - MEDIUM: 30-40% of events (unknown persons, unusual activity)
    - HIGH: 15-20% of events (genuine security concerns)

    Attributes:
        low_min: Minimum percentage for LOW events
        low_max: Maximum percentage for LOW events
        medium_min: Minimum percentage for MEDIUM events
        medium_max: Maximum percentage for MEDIUM events
        high_min: Minimum percentage for HIGH events
        high_max: Maximum percentage for HIGH events
    """

    low_min: float = 50.0
    low_max: float = 60.0
    medium_min: float = 30.0
    medium_max: float = 40.0
    high_min: float = 15.0
    high_max: float = 20.0

    def is_low_in_range(self, percentage: float) -> bool:
        """Check if LOW percentage is within target range."""
        return self.low_min <= percentage <= self.low_max

    def is_medium_in_range(self, percentage: float) -> bool:
        """Check if MEDIUM percentage is within target range."""
        return self.medium_min <= percentage <= self.medium_max

    def is_high_in_range(self, percentage: float) -> bool:
        """Check if HIGH percentage is within target range."""
        return self.high_min <= percentage <= self.high_max


# Default distribution targets
DEFAULT_TARGETS = DistributionTargets()


def classify_risk_level(score: int) -> str:
    """Classify risk level based on score thresholds.

    Thresholds:
        - LOW: score < 40
        - MEDIUM: 40 <= score < 70
        - HIGH: 70 <= score < 90
        - CRITICAL: score >= 90

    Args:
        score: Risk score from 0-100

    Returns:
        Risk level string: 'low', 'medium', 'high', or 'critical'
    """
    if score < 40:
        return "low"
    elif score < 70:
        return "medium"
    elif score < 90:
        return "high"
    else:
        return "critical"


def calculate_replay_statistics(results: list[ReplayResult]) -> ReplayStatistics:
    """Calculate aggregate statistics from replay results.

    Args:
        results: List of ReplayResult objects

    Returns:
        ReplayStatistics with aggregated metrics
    """
    if not results:
        return ReplayStatistics(
            total_events=0,
            low_count=0,
            medium_count=0,
            high_count=0,
            mean_score=0.0,
            median_score=0.0,
            std_dev=0.0,
            mean_score_diff=0.0,
            scores_decreased_count=0,
            scores_increased_count=0,
            scores_unchanged_count=0,
        )

    scores = [r.new_risk_score for r in results]
    score_diffs = [r.score_diff for r in results if r.original_risk_score is not None]

    low_count = sum(1 for s in scores if s < 40)
    medium_count = sum(1 for s in scores if 40 <= s < 70)
    high_count = sum(1 for s in scores if s >= 70)

    decreased = sum(1 for r in results if r.score_decreased)
    increased = sum(1 for r in results if r.score_increased)
    unchanged = len(results) - decreased - increased

    return ReplayStatistics(
        total_events=len(results),
        low_count=low_count,
        medium_count=medium_count,
        high_count=high_count,
        mean_score=statistics.mean(scores),
        median_score=statistics.median(scores),
        std_dev=statistics.stdev(scores) if len(scores) > 1 else 0.0,
        mean_score_diff=statistics.mean(score_diffs) if score_diffs else 0.0,
        scores_decreased_count=decreased,
        scores_increased_count=increased,
        scores_unchanged_count=unchanged,
    )


def validate_distribution(
    stats: ReplayStatistics,
    targets: DistributionTargets | None = None,
    strict: bool = False,
) -> tuple[bool, list[str]]:
    """Validate that distribution meets target ranges.

    Args:
        stats: Statistics to validate
        targets: Target distribution ranges (uses defaults if not provided)
        strict: If True, all ranges must be met; if False, allows some variance

    Returns:
        Tuple of (is_valid, list of validation messages)
    """
    if targets is None:
        targets = DEFAULT_TARGETS

    messages = []
    all_valid = True

    # Validate LOW range
    if stats.low_percentage < targets.low_min:
        messages.append(f"LOW {stats.low_percentage:.1f}% below target {targets.low_min}%")
        all_valid = False
    elif stats.low_percentage > targets.low_max:
        messages.append(f"LOW {stats.low_percentage:.1f}% above target {targets.low_max}%")
        if strict:
            all_valid = False

    # Validate MEDIUM range
    if stats.medium_percentage < targets.medium_min:
        messages.append(f"MEDIUM {stats.medium_percentage:.1f}% below target {targets.medium_min}%")
        if strict:
            all_valid = False
    elif stats.medium_percentage > targets.medium_max:
        messages.append(f"MEDIUM {stats.medium_percentage:.1f}% above target {targets.medium_max}%")
        if strict:
            all_valid = False

    # Validate HIGH range
    if stats.high_percentage > targets.high_max:
        messages.append(f"HIGH {stats.high_percentage:.1f}% above target {targets.high_max}%")
        if strict:
            all_valid = False
    elif stats.high_percentage < targets.high_min:
        messages.append(f"HIGH {stats.high_percentage:.1f}% below target {targets.high_min}%")

    if not messages:
        messages.append("Distribution meets all target ranges")

    return all_valid, messages


def generate_replay_report(
    stats: ReplayStatistics,
    experiment_name: str = "historical_replay",
    targets: DistributionTargets | None = None,
    include_validation: bool = True,
) -> dict[str, Any]:
    """Generate a comprehensive report of replay results.

    Args:
        stats: Statistics to report
        experiment_name: Name of the experiment
        targets: Target distribution ranges
        include_validation: Include distribution validation

    Returns:
        Dictionary with report data
    """
    if targets is None:
        targets = DEFAULT_TARGETS

    report: dict[str, Any] = {
        "experiment_name": experiment_name,
        "total_events": stats.total_events,
        "distribution": {
            "low": {
                "count": stats.low_count,
                "percentage": round(stats.low_percentage, 2),
                "target_range": f"{targets.low_min}-{targets.low_max}%",
                "in_range": targets.is_low_in_range(stats.low_percentage),
            },
            "medium": {
                "count": stats.medium_count,
                "percentage": round(stats.medium_percentage, 2),
                "target_range": f"{targets.medium_min}-{targets.medium_max}%",
                "in_range": targets.is_medium_in_range(stats.medium_percentage),
            },
            "high": {
                "count": stats.high_count,
                "percentage": round(stats.high_percentage, 2),
                "target_range": f"{targets.high_min}-{targets.high_max}%",
                "in_range": targets.is_high_in_range(stats.high_percentage),
            },
        },
        "score_metrics": {
            "mean": round(stats.mean_score, 2),
            "median": round(stats.median_score, 2),
            "std_dev": round(stats.std_dev, 2),
        },
        "comparison_metrics": {
            "mean_score_diff": round(stats.mean_score_diff, 2),
            "scores_decreased": stats.scores_decreased_count,
            "scores_increased": stats.scores_increased_count,
            "scores_unchanged": stats.scores_unchanged_count,
            "decrease_percentage": round(
                (stats.scores_decreased_count / stats.total_events * 100)
                if stats.total_events > 0
                else 0,
                2,
            ),
        },
    }

    if include_validation:
        is_valid, messages = validate_distribution(stats, targets)
        report["validation"] = {
            "passed": is_valid,
            "messages": messages,
        }

    return report


def create_mock_replay_result(
    event_id: int = 1,
    camera_id: str = "cam1",
    original_score: int | None = 50,
    new_score: int = 30,
    object_types: str = "person",
    detection_count: int = 1,
) -> ReplayResult:
    """Create a mock ReplayResult for testing.

    Args:
        event_id: Event database ID
        camera_id: Camera identifier
        original_score: Original risk score
        new_score: New risk score from replay
        object_types: Detected object types
        detection_count: Number of detections

    Returns:
        ReplayResult instance
    """
    return ReplayResult(
        event_id=event_id,
        camera_id=camera_id,
        original_risk_score=original_score,
        original_risk_level=classify_risk_level(original_score) if original_score else None,
        new_risk_score=new_score,
        new_risk_level=classify_risk_level(new_score),
        score_diff=abs(new_score - (original_score or 0)) if original_score else 0,
        detection_count=detection_count,
        object_types=object_types,
    )


def generate_sample_results(
    count: int = 100,
    low_pct: float = 55.0,
    medium_pct: float = 35.0,
) -> list[ReplayResult]:
    """Generate sample replay results matching a target distribution.

    Useful for testing distribution validation and statistics calculation.

    Args:
        count: Total number of results to generate
        low_pct: Percentage of LOW results
        medium_pct: Percentage of MEDIUM results
        (HIGH percentage = 100 - low_pct - medium_pct)

    Returns:
        List of ReplayResult instances
    """
    results = []
    low_count = int(count * low_pct / 100)
    medium_count = int(count * medium_pct / 100)
    high_count = count - low_count - medium_count

    # Generate LOW results
    for i in range(low_count):
        score = 20 + (i % 20)  # 20-39 range
        results.append(
            create_mock_replay_result(
                event_id=i,
                original_score=60,
                new_score=score,
            )
        )

    # Generate MEDIUM results
    for i in range(medium_count):
        score = 45 + (i % 25)  # 45-69 range
        results.append(
            create_mock_replay_result(
                event_id=low_count + i,
                original_score=60,
                new_score=score,
            )
        )

    # Generate HIGH results
    for i in range(high_count):
        score = 75 + (i % 20)  # 75-94 range
        results.append(
            create_mock_replay_result(
                event_id=low_count + medium_count + i,
                original_score=60,
                new_score=score,
            )
        )

    return results
