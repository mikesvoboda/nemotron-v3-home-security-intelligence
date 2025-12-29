"""Enumeration types for home security intelligence system."""

from enum import Enum


class Severity(str, Enum):
    """Severity levels for security events.

    Severity is determined by mapping risk scores (0-100) to these levels:
    - LOW: Routine activity, no concern (default: 0-29)
    - MEDIUM: Notable activity, worth reviewing (default: 30-59)
    - HIGH: Concerning activity, review soon (default: 60-84)
    - CRITICAL: Immediate attention required (default: 85-100)

    The thresholds are configurable via settings:
    - SEVERITY_LOW_MAX (default: 29)
    - SEVERITY_MEDIUM_MAX (default: 59)
    - SEVERITY_HIGH_MAX (default: 84)
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    def __str__(self) -> str:
        """Return string representation of severity."""
        return self.value
