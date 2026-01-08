"""Severity service for risk score mapping and severity utilities.

This module provides the SeverityService class for mapping risk scores to
severity levels, along with utility functions for working with severity values.

The severity taxonomy defines four levels:
- LOW: Routine activity, no concern (default: 0-29)
- MEDIUM: Notable activity, worth reviewing (default: 30-59)
- HIGH: Concerning activity, review soon (default: 60-84)
- CRITICAL: Immediate attention required (default: 85-100)

Thresholds are configurable via environment variables:
- SEVERITY_LOW_MAX (default: 29)
- SEVERITY_MEDIUM_MAX (default: 59)
- SEVERITY_HIGH_MAX (default: 84)
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from backend.core.config import get_settings
from backend.models.enums import Severity

# Color scheme for severity levels (Tailwind-inspired)
SEVERITY_COLORS: dict[Severity, str] = {
    Severity.LOW: "#22c55e",  # green-500
    Severity.MEDIUM: "#eab308",  # yellow-500
    Severity.HIGH: "#f97316",  # orange-500
    Severity.CRITICAL: "#ef4444",  # red-500
}

# Sort priority (lower = higher priority, critical should appear first)
SEVERITY_PRIORITY: dict[Severity, int] = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
}


@dataclass(frozen=True, slots=True)
class SeverityDefinition:
    """Definition of a severity level with its metadata.

    Attributes:
        severity: The severity enum value
        label: Human-readable label
        description: Detailed description of when this severity applies
        color: Hex color code for UI display
        priority: Sort priority (0 = highest priority)
        min_score: Minimum risk score for this severity (inclusive)
        max_score: Maximum risk score for this severity (inclusive)
    """

    severity: Severity
    label: str
    description: str
    color: str
    priority: int
    min_score: int
    max_score: int

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "severity": self.severity.value,
            "label": self.label,
            "description": self.description,
            "color": self.color,
            "priority": self.priority,
            "min_score": self.min_score,
            "max_score": self.max_score,
        }


class SeverityService:
    """Service for severity-related operations.

    This service provides methods for:
    - Mapping risk scores to severity levels
    - Getting severity metadata
    - Getting configurable thresholds

    The service reads thresholds from application settings, allowing runtime
    configuration via environment variables.
    """

    def __init__(
        self,
        low_max: int | None = None,
        medium_max: int | None = None,
        high_max: int | None = None,
    ) -> None:
        """Initialize the severity service.

        Args:
            low_max: Maximum score for LOW severity (default: from settings)
            medium_max: Maximum score for MEDIUM severity (default: from settings)
            high_max: Maximum score for HIGH severity (default: from settings)
        """
        settings = get_settings()

        self.low_max = low_max if low_max is not None else settings.severity_low_max
        self.medium_max = medium_max if medium_max is not None else settings.severity_medium_max
        self.high_max = high_max if high_max is not None else settings.severity_high_max

        # Validate threshold ordering
        if not (0 <= self.low_max < self.medium_max < self.high_max <= 100):
            raise ValueError(
                f"Invalid severity thresholds: low_max={self.low_max}, "
                f"medium_max={self.medium_max}, high_max={self.high_max}. "
                "Must satisfy: 0 <= low_max < medium_max < high_max <= 100"
            )

    def risk_score_to_severity(self, score: int) -> Severity:
        """Map a risk score (0-100) to a severity level.

        Uses Python 3.10+ structural pattern matching with guard clauses
        for clear, readable threshold-based classification.

        Args:
            score: Risk score from 0 to 100

        Returns:
            Severity level corresponding to the risk score

        Raises:
            ValueError: If score is outside the 0-100 range
        """
        if not 0 <= score <= 100:
            raise ValueError(f"Risk score must be between 0 and 100, got {score}")

        match score:
            case _ if score <= self.low_max:
                return Severity.LOW
            case _ if score <= self.medium_max:
                return Severity.MEDIUM
            case _ if score <= self.high_max:
                return Severity.HIGH
            case _:
                return Severity.CRITICAL

    def get_severity_definitions(self) -> list[SeverityDefinition]:
        """Get all severity definitions with current thresholds.

        Returns:
            List of SeverityDefinition objects for all severity levels
        """
        return [
            SeverityDefinition(
                severity=Severity.LOW,
                label="Low",
                description="Routine activity, no concern",
                color=SEVERITY_COLORS[Severity.LOW],
                priority=SEVERITY_PRIORITY[Severity.LOW],
                min_score=0,
                max_score=self.low_max,
            ),
            SeverityDefinition(
                severity=Severity.MEDIUM,
                label="Medium",
                description="Notable activity, worth reviewing",
                color=SEVERITY_COLORS[Severity.MEDIUM],
                priority=SEVERITY_PRIORITY[Severity.MEDIUM],
                min_score=self.low_max + 1,
                max_score=self.medium_max,
            ),
            SeverityDefinition(
                severity=Severity.HIGH,
                label="High",
                description="Concerning activity, review soon",
                color=SEVERITY_COLORS[Severity.HIGH],
                priority=SEVERITY_PRIORITY[Severity.HIGH],
                min_score=self.medium_max + 1,
                max_score=self.high_max,
            ),
            SeverityDefinition(
                severity=Severity.CRITICAL,
                label="Critical",
                description="Immediate attention required",
                color=SEVERITY_COLORS[Severity.CRITICAL],
                priority=SEVERITY_PRIORITY[Severity.CRITICAL],
                min_score=self.high_max + 1,
                max_score=100,
            ),
        ]

    def get_thresholds(self) -> dict[str, int]:
        """Get current severity thresholds.

        Returns:
            Dictionary with threshold values
        """
        return {
            "low_max": self.low_max,
            "medium_max": self.medium_max,
            "high_max": self.high_max,
        }


# =============================================================================
# Utility Functions
# =============================================================================


def get_severity_color(severity: Severity) -> str:
    """Get the hex color code for a severity level.

    Args:
        severity: The severity level

    Returns:
        Hex color code (e.g., "#22c55e")
    """
    return SEVERITY_COLORS.get(severity, SEVERITY_COLORS[Severity.LOW])


def get_severity_priority(severity: Severity) -> int:
    """Get the sort priority for a severity level.

    Lower values indicate higher priority (critical=0, low=3).

    Args:
        severity: The severity level

    Returns:
        Sort priority as integer (0 = highest priority)
    """
    return SEVERITY_PRIORITY.get(severity, SEVERITY_PRIORITY[Severity.LOW])


def severity_gte(a: Severity, b: Severity) -> bool:
    """Check if severity a is greater than or equal to severity b.

    "Greater" means more severe (critical > high > medium > low).

    Args:
        a: First severity level
        b: Second severity level

    Returns:
        True if a is at least as severe as b
    """
    # Lower priority number = higher severity
    return get_severity_priority(a) <= get_severity_priority(b)


def severity_gt(a: Severity, b: Severity) -> bool:
    """Check if severity a is strictly greater than severity b.

    "Greater" means more severe (critical > high > medium > low).

    Args:
        a: First severity level
        b: Second severity level

    Returns:
        True if a is more severe than b
    """
    return get_severity_priority(a) < get_severity_priority(b)


def severity_lte(a: Severity, b: Severity) -> bool:
    """Check if severity a is less than or equal to severity b.

    "Less" means less severe (low < medium < high < critical).

    Args:
        a: First severity level
        b: Second severity level

    Returns:
        True if a is at most as severe as b
    """
    return get_severity_priority(a) >= get_severity_priority(b)


def severity_lt(a: Severity, b: Severity) -> bool:
    """Check if severity a is strictly less than severity b.

    "Less" means less severe (low < medium < high < critical).

    Args:
        a: First severity level
        b: Second severity level

    Returns:
        True if a is less severe than b
    """
    return get_severity_priority(a) > get_severity_priority(b)


def severity_from_string(value: str) -> Severity:
    """Convert a string to a Severity enum value.

    Args:
        value: String representation of severity (case-insensitive)

    Returns:
        Corresponding Severity enum value

    Raises:
        ValueError: If the string doesn't match any severity level
    """
    try:
        return Severity(value.lower())
    except ValueError as e:
        valid_values = [s.value for s in Severity]
        raise ValueError(
            f"Invalid severity value: {value!r}. Must be one of: {valid_values}"
        ) from e


@lru_cache(maxsize=1)
def get_severity_service() -> SeverityService:
    """Get a cached SeverityService instance.

    Returns:
        SeverityService instance configured from settings
    """
    return SeverityService()


def reset_severity_service() -> None:
    """Clear the cached SeverityService instance.

    Call this after changing severity threshold settings to ensure
    the service picks up the new configuration.
    """
    get_severity_service.cache_clear()
