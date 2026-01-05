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
from collections.abc import Callable
from inspect import signature as _mutmut_signature
from typing import Annotated, ClassVar

MutantDict = Annotated[dict[str, Callable], "Mutant"]


def _mutmut_trampoline(orig, mutants, call_args, call_kwargs, self_arg=None):
    """Forward call to original or mutated function, depending on the environment"""
    import os

    mutant_under_test = os.environ["MUTANT_UNDER_TEST"]
    if mutant_under_test == "fail":
        from mutmut.__main__ import MutmutProgrammaticFailException

        raise MutmutProgrammaticFailException("Failed programmatically")
    elif mutant_under_test == "stats":
        from mutmut.__main__ import record_trampoline_hit

        record_trampoline_hit(orig.__module__ + "." + orig.__name__)
        result = orig(*call_args, **call_kwargs)
        return result
    prefix = orig.__module__ + "." + orig.__name__ + "__mutmut_"
    if not mutant_under_test.startswith(prefix):
        result = orig(*call_args, **call_kwargs)
        return result
    mutant_name = mutant_under_test.rpartition(".")[-1]
    if self_arg is not None:
        # call to a class method where self is not bound
        result = mutants[mutant_name](self_arg, *call_args, **call_kwargs)
    else:
        result = mutants[mutant_name](*call_args, **call_kwargs)
    return result


@dataclass(frozen=True)
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

    def xǁSeverityServiceǁ__init____mutmut_orig(
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

    def xǁSeverityServiceǁ__init____mutmut_1(
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
        settings = None

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

    def xǁSeverityServiceǁ__init____mutmut_2(
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

        self.low_max = None
        self.medium_max = medium_max if medium_max is not None else settings.severity_medium_max
        self.high_max = high_max if high_max is not None else settings.severity_high_max

        # Validate threshold ordering
        if not (0 <= self.low_max < self.medium_max < self.high_max <= 100):
            raise ValueError(
                f"Invalid severity thresholds: low_max={self.low_max}, "
                f"medium_max={self.medium_max}, high_max={self.high_max}. "
                "Must satisfy: 0 <= low_max < medium_max < high_max <= 100"
            )

    def xǁSeverityServiceǁ__init____mutmut_3(
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

        self.low_max = low_max if low_max is None else settings.severity_low_max
        self.medium_max = medium_max if medium_max is not None else settings.severity_medium_max
        self.high_max = high_max if high_max is not None else settings.severity_high_max

        # Validate threshold ordering
        if not (0 <= self.low_max < self.medium_max < self.high_max <= 100):
            raise ValueError(
                f"Invalid severity thresholds: low_max={self.low_max}, "
                f"medium_max={self.medium_max}, high_max={self.high_max}. "
                "Must satisfy: 0 <= low_max < medium_max < high_max <= 100"
            )

    def xǁSeverityServiceǁ__init____mutmut_4(
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
        self.medium_max = None
        self.high_max = high_max if high_max is not None else settings.severity_high_max

        # Validate threshold ordering
        if not (0 <= self.low_max < self.medium_max < self.high_max <= 100):
            raise ValueError(
                f"Invalid severity thresholds: low_max={self.low_max}, "
                f"medium_max={self.medium_max}, high_max={self.high_max}. "
                "Must satisfy: 0 <= low_max < medium_max < high_max <= 100"
            )

    def xǁSeverityServiceǁ__init____mutmut_5(
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
        self.medium_max = medium_max if medium_max is None else settings.severity_medium_max
        self.high_max = high_max if high_max is not None else settings.severity_high_max

        # Validate threshold ordering
        if not (0 <= self.low_max < self.medium_max < self.high_max <= 100):
            raise ValueError(
                f"Invalid severity thresholds: low_max={self.low_max}, "
                f"medium_max={self.medium_max}, high_max={self.high_max}. "
                "Must satisfy: 0 <= low_max < medium_max < high_max <= 100"
            )

    def xǁSeverityServiceǁ__init____mutmut_6(
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
        self.high_max = None

        # Validate threshold ordering
        if not (0 <= self.low_max < self.medium_max < self.high_max <= 100):
            raise ValueError(
                f"Invalid severity thresholds: low_max={self.low_max}, "
                f"medium_max={self.medium_max}, high_max={self.high_max}. "
                "Must satisfy: 0 <= low_max < medium_max < high_max <= 100"
            )

    def xǁSeverityServiceǁ__init____mutmut_7(
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
        self.high_max = high_max if high_max is None else settings.severity_high_max

        # Validate threshold ordering
        if not (0 <= self.low_max < self.medium_max < self.high_max <= 100):
            raise ValueError(
                f"Invalid severity thresholds: low_max={self.low_max}, "
                f"medium_max={self.medium_max}, high_max={self.high_max}. "
                "Must satisfy: 0 <= low_max < medium_max < high_max <= 100"
            )

    def xǁSeverityServiceǁ__init____mutmut_8(
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
        if 0 <= self.low_max < self.medium_max < self.high_max <= 100:
            raise ValueError(
                f"Invalid severity thresholds: low_max={self.low_max}, "
                f"medium_max={self.medium_max}, high_max={self.high_max}. "
                "Must satisfy: 0 <= low_max < medium_max < high_max <= 100"
            )

    def xǁSeverityServiceǁ__init____mutmut_9(
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
        if not (1 <= self.low_max < self.medium_max < self.high_max <= 100):
            raise ValueError(
                f"Invalid severity thresholds: low_max={self.low_max}, "
                f"medium_max={self.medium_max}, high_max={self.high_max}. "
                "Must satisfy: 0 <= low_max < medium_max < high_max <= 100"
            )

    def xǁSeverityServiceǁ__init____mutmut_10(
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
        if not (0 < self.low_max < self.medium_max < self.high_max <= 100):
            raise ValueError(
                f"Invalid severity thresholds: low_max={self.low_max}, "
                f"medium_max={self.medium_max}, high_max={self.high_max}. "
                "Must satisfy: 0 <= low_max < medium_max < high_max <= 100"
            )

    def xǁSeverityServiceǁ__init____mutmut_11(
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
        if not (0 <= self.low_max <= self.medium_max < self.high_max <= 100):
            raise ValueError(
                f"Invalid severity thresholds: low_max={self.low_max}, "
                f"medium_max={self.medium_max}, high_max={self.high_max}. "
                "Must satisfy: 0 <= low_max < medium_max < high_max <= 100"
            )

    def xǁSeverityServiceǁ__init____mutmut_12(
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
        if not (0 <= self.low_max < self.medium_max <= self.high_max <= 100):
            raise ValueError(
                f"Invalid severity thresholds: low_max={self.low_max}, "
                f"medium_max={self.medium_max}, high_max={self.high_max}. "
                "Must satisfy: 0 <= low_max < medium_max < high_max <= 100"
            )

    def xǁSeverityServiceǁ__init____mutmut_13(
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
        if not (0 <= self.low_max < self.medium_max < self.high_max < 100):
            raise ValueError(
                f"Invalid severity thresholds: low_max={self.low_max}, "
                f"medium_max={self.medium_max}, high_max={self.high_max}. "
                "Must satisfy: 0 <= low_max < medium_max < high_max <= 100"
            )

    def xǁSeverityServiceǁ__init____mutmut_14(
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
        if not (0 <= self.low_max < self.medium_max < self.high_max <= 101):
            raise ValueError(
                f"Invalid severity thresholds: low_max={self.low_max}, "
                f"medium_max={self.medium_max}, high_max={self.high_max}. "
                "Must satisfy: 0 <= low_max < medium_max < high_max <= 100"
            )

    def xǁSeverityServiceǁ__init____mutmut_15(
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
            raise ValueError(None)

    def xǁSeverityServiceǁ__init____mutmut_16(
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
                "XXMust satisfy: 0 <= low_max < medium_max < high_max <= 100XX"
            )

    def xǁSeverityServiceǁ__init____mutmut_17(
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
                "must satisfy: 0 <= low_max < medium_max < high_max <= 100"
            )

    def xǁSeverityServiceǁ__init____mutmut_18(
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
                "MUST SATISFY: 0 <= LOW_MAX < MEDIUM_MAX < HIGH_MAX <= 100"
            )

    xǁSeverityServiceǁ__init____mutmut_mutants: ClassVar[MutantDict] = {
        "xǁSeverityServiceǁ__init____mutmut_1": xǁSeverityServiceǁ__init____mutmut_1,
        "xǁSeverityServiceǁ__init____mutmut_2": xǁSeverityServiceǁ__init____mutmut_2,
        "xǁSeverityServiceǁ__init____mutmut_3": xǁSeverityServiceǁ__init____mutmut_3,
        "xǁSeverityServiceǁ__init____mutmut_4": xǁSeverityServiceǁ__init____mutmut_4,
        "xǁSeverityServiceǁ__init____mutmut_5": xǁSeverityServiceǁ__init____mutmut_5,
        "xǁSeverityServiceǁ__init____mutmut_6": xǁSeverityServiceǁ__init____mutmut_6,
        "xǁSeverityServiceǁ__init____mutmut_7": xǁSeverityServiceǁ__init____mutmut_7,
        "xǁSeverityServiceǁ__init____mutmut_8": xǁSeverityServiceǁ__init____mutmut_8,
        "xǁSeverityServiceǁ__init____mutmut_9": xǁSeverityServiceǁ__init____mutmut_9,
        "xǁSeverityServiceǁ__init____mutmut_10": xǁSeverityServiceǁ__init____mutmut_10,
        "xǁSeverityServiceǁ__init____mutmut_11": xǁSeverityServiceǁ__init____mutmut_11,
        "xǁSeverityServiceǁ__init____mutmut_12": xǁSeverityServiceǁ__init____mutmut_12,
        "xǁSeverityServiceǁ__init____mutmut_13": xǁSeverityServiceǁ__init____mutmut_13,
        "xǁSeverityServiceǁ__init____mutmut_14": xǁSeverityServiceǁ__init____mutmut_14,
        "xǁSeverityServiceǁ__init____mutmut_15": xǁSeverityServiceǁ__init____mutmut_15,
        "xǁSeverityServiceǁ__init____mutmut_16": xǁSeverityServiceǁ__init____mutmut_16,
        "xǁSeverityServiceǁ__init____mutmut_17": xǁSeverityServiceǁ__init____mutmut_17,
        "xǁSeverityServiceǁ__init____mutmut_18": xǁSeverityServiceǁ__init____mutmut_18,
    }

    def __init__(self, *args, **kwargs):
        result = _mutmut_trampoline(
            object.__getattribute__(self, "xǁSeverityServiceǁ__init____mutmut_orig"),
            object.__getattribute__(self, "xǁSeverityServiceǁ__init____mutmut_mutants"),
            args,
            kwargs,
            self,
        )
        return result

    __init__.__signature__ = _mutmut_signature(xǁSeverityServiceǁ__init____mutmut_orig)
    xǁSeverityServiceǁ__init____mutmut_orig.__name__ = "xǁSeverityServiceǁ__init__"

    def xǁSeverityServiceǁrisk_score_to_severity__mutmut_orig(self, score: int) -> Severity:
        """Map a risk score (0-100) to a severity level.

        Args:
            score: Risk score from 0 to 100

        Returns:
            Severity level corresponding to the risk score

        Raises:
            ValueError: If score is outside the 0-100 range
        """
        if not 0 <= score <= 100:
            raise ValueError(f"Risk score must be between 0 and 100, got {score}")

        if score <= self.low_max:
            return Severity.LOW
        elif score <= self.medium_max:
            return Severity.MEDIUM
        elif score <= self.high_max:
            return Severity.HIGH
        else:
            return Severity.CRITICAL

    def xǁSeverityServiceǁrisk_score_to_severity__mutmut_1(self, score: int) -> Severity:
        """Map a risk score (0-100) to a severity level.

        Args:
            score: Risk score from 0 to 100

        Returns:
            Severity level corresponding to the risk score

        Raises:
            ValueError: If score is outside the 0-100 range
        """
        if 0 <= score <= 100:
            raise ValueError(f"Risk score must be between 0 and 100, got {score}")

        if score <= self.low_max:
            return Severity.LOW
        elif score <= self.medium_max:
            return Severity.MEDIUM
        elif score <= self.high_max:
            return Severity.HIGH
        else:
            return Severity.CRITICAL

    def xǁSeverityServiceǁrisk_score_to_severity__mutmut_2(self, score: int) -> Severity:
        """Map a risk score (0-100) to a severity level.

        Args:
            score: Risk score from 0 to 100

        Returns:
            Severity level corresponding to the risk score

        Raises:
            ValueError: If score is outside the 0-100 range
        """
        if not 1 <= score <= 100:
            raise ValueError(f"Risk score must be between 0 and 100, got {score}")

        if score <= self.low_max:
            return Severity.LOW
        elif score <= self.medium_max:
            return Severity.MEDIUM
        elif score <= self.high_max:
            return Severity.HIGH
        else:
            return Severity.CRITICAL

    def xǁSeverityServiceǁrisk_score_to_severity__mutmut_3(self, score: int) -> Severity:
        """Map a risk score (0-100) to a severity level.

        Args:
            score: Risk score from 0 to 100

        Returns:
            Severity level corresponding to the risk score

        Raises:
            ValueError: If score is outside the 0-100 range
        """
        if not 0 < score <= 100:
            raise ValueError(f"Risk score must be between 0 and 100, got {score}")

        if score <= self.low_max:
            return Severity.LOW
        elif score <= self.medium_max:
            return Severity.MEDIUM
        elif score <= self.high_max:
            return Severity.HIGH
        else:
            return Severity.CRITICAL

    def xǁSeverityServiceǁrisk_score_to_severity__mutmut_4(self, score: int) -> Severity:
        """Map a risk score (0-100) to a severity level.

        Args:
            score: Risk score from 0 to 100

        Returns:
            Severity level corresponding to the risk score

        Raises:
            ValueError: If score is outside the 0-100 range
        """
        if not 0 <= score < 100:
            raise ValueError(f"Risk score must be between 0 and 100, got {score}")

        if score <= self.low_max:
            return Severity.LOW
        elif score <= self.medium_max:
            return Severity.MEDIUM
        elif score <= self.high_max:
            return Severity.HIGH
        else:
            return Severity.CRITICAL

    def xǁSeverityServiceǁrisk_score_to_severity__mutmut_5(self, score: int) -> Severity:
        """Map a risk score (0-100) to a severity level.

        Args:
            score: Risk score from 0 to 100

        Returns:
            Severity level corresponding to the risk score

        Raises:
            ValueError: If score is outside the 0-100 range
        """
        if not 0 <= score <= 101:
            raise ValueError(f"Risk score must be between 0 and 100, got {score}")

        if score <= self.low_max:
            return Severity.LOW
        elif score <= self.medium_max:
            return Severity.MEDIUM
        elif score <= self.high_max:
            return Severity.HIGH
        else:
            return Severity.CRITICAL

    def xǁSeverityServiceǁrisk_score_to_severity__mutmut_6(self, score: int) -> Severity:
        """Map a risk score (0-100) to a severity level.

        Args:
            score: Risk score from 0 to 100

        Returns:
            Severity level corresponding to the risk score

        Raises:
            ValueError: If score is outside the 0-100 range
        """
        if not 0 <= score <= 100:
            raise ValueError(None)

        if score <= self.low_max:
            return Severity.LOW
        elif score <= self.medium_max:
            return Severity.MEDIUM
        elif score <= self.high_max:
            return Severity.HIGH
        else:
            return Severity.CRITICAL

    def xǁSeverityServiceǁrisk_score_to_severity__mutmut_7(self, score: int) -> Severity:
        """Map a risk score (0-100) to a severity level.

        Args:
            score: Risk score from 0 to 100

        Returns:
            Severity level corresponding to the risk score

        Raises:
            ValueError: If score is outside the 0-100 range
        """
        if not 0 <= score <= 100:
            raise ValueError(f"Risk score must be between 0 and 100, got {score}")

        if score < self.low_max:
            return Severity.LOW
        elif score <= self.medium_max:
            return Severity.MEDIUM
        elif score <= self.high_max:
            return Severity.HIGH
        else:
            return Severity.CRITICAL

    def xǁSeverityServiceǁrisk_score_to_severity__mutmut_8(self, score: int) -> Severity:
        """Map a risk score (0-100) to a severity level.

        Args:
            score: Risk score from 0 to 100

        Returns:
            Severity level corresponding to the risk score

        Raises:
            ValueError: If score is outside the 0-100 range
        """
        if not 0 <= score <= 100:
            raise ValueError(f"Risk score must be between 0 and 100, got {score}")

        if score <= self.low_max:
            return Severity.LOW
        elif score < self.medium_max:
            return Severity.MEDIUM
        elif score <= self.high_max:
            return Severity.HIGH
        else:
            return Severity.CRITICAL

    def xǁSeverityServiceǁrisk_score_to_severity__mutmut_9(self, score: int) -> Severity:
        """Map a risk score (0-100) to a severity level.

        Args:
            score: Risk score from 0 to 100

        Returns:
            Severity level corresponding to the risk score

        Raises:
            ValueError: If score is outside the 0-100 range
        """
        if not 0 <= score <= 100:
            raise ValueError(f"Risk score must be between 0 and 100, got {score}")

        if score <= self.low_max:
            return Severity.LOW
        elif score <= self.medium_max:
            return Severity.MEDIUM
        elif score < self.high_max:
            return Severity.HIGH
        else:
            return Severity.CRITICAL

    xǁSeverityServiceǁrisk_score_to_severity__mutmut_mutants: ClassVar[MutantDict] = {
        "xǁSeverityServiceǁrisk_score_to_severity__mutmut_1": xǁSeverityServiceǁrisk_score_to_severity__mutmut_1,
        "xǁSeverityServiceǁrisk_score_to_severity__mutmut_2": xǁSeverityServiceǁrisk_score_to_severity__mutmut_2,
        "xǁSeverityServiceǁrisk_score_to_severity__mutmut_3": xǁSeverityServiceǁrisk_score_to_severity__mutmut_3,
        "xǁSeverityServiceǁrisk_score_to_severity__mutmut_4": xǁSeverityServiceǁrisk_score_to_severity__mutmut_4,
        "xǁSeverityServiceǁrisk_score_to_severity__mutmut_5": xǁSeverityServiceǁrisk_score_to_severity__mutmut_5,
        "xǁSeverityServiceǁrisk_score_to_severity__mutmut_6": xǁSeverityServiceǁrisk_score_to_severity__mutmut_6,
        "xǁSeverityServiceǁrisk_score_to_severity__mutmut_7": xǁSeverityServiceǁrisk_score_to_severity__mutmut_7,
        "xǁSeverityServiceǁrisk_score_to_severity__mutmut_8": xǁSeverityServiceǁrisk_score_to_severity__mutmut_8,
        "xǁSeverityServiceǁrisk_score_to_severity__mutmut_9": xǁSeverityServiceǁrisk_score_to_severity__mutmut_9,
    }

    def risk_score_to_severity(self, *args, **kwargs):
        result = _mutmut_trampoline(
            object.__getattribute__(self, "xǁSeverityServiceǁrisk_score_to_severity__mutmut_orig"),
            object.__getattribute__(
                self, "xǁSeverityServiceǁrisk_score_to_severity__mutmut_mutants"
            ),
            args,
            kwargs,
            self,
        )
        return result

    risk_score_to_severity.__signature__ = _mutmut_signature(
        xǁSeverityServiceǁrisk_score_to_severity__mutmut_orig
    )
    xǁSeverityServiceǁrisk_score_to_severity__mutmut_orig.__name__ = (
        "xǁSeverityServiceǁrisk_score_to_severity"
    )

    def xǁSeverityServiceǁget_severity_definitions__mutmut_orig(self) -> list[SeverityDefinition]:
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_1(self) -> list[SeverityDefinition]:
        """Get all severity definitions with current thresholds.

        Returns:
            List of SeverityDefinition objects for all severity levels
        """
        return [
            SeverityDefinition(
                severity=None,
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_2(self) -> list[SeverityDefinition]:
        """Get all severity definitions with current thresholds.

        Returns:
            List of SeverityDefinition objects for all severity levels
        """
        return [
            SeverityDefinition(
                severity=Severity.LOW,
                label=None,
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_3(self) -> list[SeverityDefinition]:
        """Get all severity definitions with current thresholds.

        Returns:
            List of SeverityDefinition objects for all severity levels
        """
        return [
            SeverityDefinition(
                severity=Severity.LOW,
                label="Low",
                description=None,
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_4(self) -> list[SeverityDefinition]:
        """Get all severity definitions with current thresholds.

        Returns:
            List of SeverityDefinition objects for all severity levels
        """
        return [
            SeverityDefinition(
                severity=Severity.LOW,
                label="Low",
                description="Routine activity, no concern",
                color=None,
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_5(self) -> list[SeverityDefinition]:
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
                priority=None,
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_6(self) -> list[SeverityDefinition]:
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
                min_score=None,
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_7(self) -> list[SeverityDefinition]:
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
                max_score=None,
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_8(self) -> list[SeverityDefinition]:
        """Get all severity definitions with current thresholds.

        Returns:
            List of SeverityDefinition objects for all severity levels
        """
        return [
            SeverityDefinition(
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_9(self) -> list[SeverityDefinition]:
        """Get all severity definitions with current thresholds.

        Returns:
            List of SeverityDefinition objects for all severity levels
        """
        return [
            SeverityDefinition(
                severity=Severity.LOW,
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_10(self) -> list[SeverityDefinition]:
        """Get all severity definitions with current thresholds.

        Returns:
            List of SeverityDefinition objects for all severity levels
        """
        return [
            SeverityDefinition(
                severity=Severity.LOW,
                label="Low",
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_11(self) -> list[SeverityDefinition]:
        """Get all severity definitions with current thresholds.

        Returns:
            List of SeverityDefinition objects for all severity levels
        """
        return [
            SeverityDefinition(
                severity=Severity.LOW,
                label="Low",
                description="Routine activity, no concern",
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_12(self) -> list[SeverityDefinition]:
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_13(self) -> list[SeverityDefinition]:
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_14(self) -> list[SeverityDefinition]:
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_15(self) -> list[SeverityDefinition]:
        """Get all severity definitions with current thresholds.

        Returns:
            List of SeverityDefinition objects for all severity levels
        """
        return [
            SeverityDefinition(
                severity=Severity.LOW,
                label="XXLowXX",
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_16(self) -> list[SeverityDefinition]:
        """Get all severity definitions with current thresholds.

        Returns:
            List of SeverityDefinition objects for all severity levels
        """
        return [
            SeverityDefinition(
                severity=Severity.LOW,
                label="low",
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_17(self) -> list[SeverityDefinition]:
        """Get all severity definitions with current thresholds.

        Returns:
            List of SeverityDefinition objects for all severity levels
        """
        return [
            SeverityDefinition(
                severity=Severity.LOW,
                label="LOW",
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_18(self) -> list[SeverityDefinition]:
        """Get all severity definitions with current thresholds.

        Returns:
            List of SeverityDefinition objects for all severity levels
        """
        return [
            SeverityDefinition(
                severity=Severity.LOW,
                label="Low",
                description="XXRoutine activity, no concernXX",
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_19(self) -> list[SeverityDefinition]:
        """Get all severity definitions with current thresholds.

        Returns:
            List of SeverityDefinition objects for all severity levels
        """
        return [
            SeverityDefinition(
                severity=Severity.LOW,
                label="Low",
                description="routine activity, no concern",
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_20(self) -> list[SeverityDefinition]:
        """Get all severity definitions with current thresholds.

        Returns:
            List of SeverityDefinition objects for all severity levels
        """
        return [
            SeverityDefinition(
                severity=Severity.LOW,
                label="Low",
                description="ROUTINE ACTIVITY, NO CONCERN",
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_21(self) -> list[SeverityDefinition]:
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
                min_score=1,
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_22(self) -> list[SeverityDefinition]:
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
                severity=None,
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_23(self) -> list[SeverityDefinition]:
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
                label=None,
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_24(self) -> list[SeverityDefinition]:
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
                description=None,
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_25(self) -> list[SeverityDefinition]:
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
                color=None,
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_26(self) -> list[SeverityDefinition]:
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
                priority=None,
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_27(self) -> list[SeverityDefinition]:
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
                min_score=None,
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_28(self) -> list[SeverityDefinition]:
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
                max_score=None,
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_29(self) -> list[SeverityDefinition]:
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_30(self) -> list[SeverityDefinition]:
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_31(self) -> list[SeverityDefinition]:
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_32(self) -> list[SeverityDefinition]:
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_33(self) -> list[SeverityDefinition]:
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_34(self) -> list[SeverityDefinition]:
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_35(self) -> list[SeverityDefinition]:
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_36(self) -> list[SeverityDefinition]:
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
                label="XXMediumXX",
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_37(self) -> list[SeverityDefinition]:
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
                label="medium",
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_38(self) -> list[SeverityDefinition]:
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
                label="MEDIUM",
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_39(self) -> list[SeverityDefinition]:
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
                description="XXNotable activity, worth reviewingXX",
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_40(self) -> list[SeverityDefinition]:
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
                description="notable activity, worth reviewing",
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_41(self) -> list[SeverityDefinition]:
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
                description="NOTABLE ACTIVITY, WORTH REVIEWING",
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_42(self) -> list[SeverityDefinition]:
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
                min_score=self.low_max - 1,
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_43(self) -> list[SeverityDefinition]:
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
                min_score=self.low_max + 2,
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_44(self) -> list[SeverityDefinition]:
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
                severity=None,
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_45(self) -> list[SeverityDefinition]:
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
                label=None,
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_46(self) -> list[SeverityDefinition]:
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
                description=None,
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_47(self) -> list[SeverityDefinition]:
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
                color=None,
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_48(self) -> list[SeverityDefinition]:
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
                priority=None,
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_49(self) -> list[SeverityDefinition]:
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
                min_score=None,
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_50(self) -> list[SeverityDefinition]:
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
                max_score=None,
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_51(self) -> list[SeverityDefinition]:
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_52(self) -> list[SeverityDefinition]:
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_53(self) -> list[SeverityDefinition]:
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_54(self) -> list[SeverityDefinition]:
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_55(self) -> list[SeverityDefinition]:
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_56(self) -> list[SeverityDefinition]:
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_57(self) -> list[SeverityDefinition]:
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_58(self) -> list[SeverityDefinition]:
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
                label="XXHighXX",
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_59(self) -> list[SeverityDefinition]:
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
                label="high",
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_60(self) -> list[SeverityDefinition]:
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
                label="HIGH",
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_61(self) -> list[SeverityDefinition]:
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
                description="XXConcerning activity, review soonXX",
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_62(self) -> list[SeverityDefinition]:
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
                description="concerning activity, review soon",
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_63(self) -> list[SeverityDefinition]:
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
                description="CONCERNING ACTIVITY, REVIEW SOON",
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_64(self) -> list[SeverityDefinition]:
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
                min_score=self.medium_max - 1,
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_65(self) -> list[SeverityDefinition]:
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
                min_score=self.medium_max + 2,
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

    def xǁSeverityServiceǁget_severity_definitions__mutmut_66(self) -> list[SeverityDefinition]:
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
                severity=None,
                label="Critical",
                description="Immediate attention required",
                color=SEVERITY_COLORS[Severity.CRITICAL],
                priority=SEVERITY_PRIORITY[Severity.CRITICAL],
                min_score=self.high_max + 1,
                max_score=100,
            ),
        ]

    def xǁSeverityServiceǁget_severity_definitions__mutmut_67(self) -> list[SeverityDefinition]:
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
                label=None,
                description="Immediate attention required",
                color=SEVERITY_COLORS[Severity.CRITICAL],
                priority=SEVERITY_PRIORITY[Severity.CRITICAL],
                min_score=self.high_max + 1,
                max_score=100,
            ),
        ]

    def xǁSeverityServiceǁget_severity_definitions__mutmut_68(self) -> list[SeverityDefinition]:
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
                description=None,
                color=SEVERITY_COLORS[Severity.CRITICAL],
                priority=SEVERITY_PRIORITY[Severity.CRITICAL],
                min_score=self.high_max + 1,
                max_score=100,
            ),
        ]

    def xǁSeverityServiceǁget_severity_definitions__mutmut_69(self) -> list[SeverityDefinition]:
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
                color=None,
                priority=SEVERITY_PRIORITY[Severity.CRITICAL],
                min_score=self.high_max + 1,
                max_score=100,
            ),
        ]

    def xǁSeverityServiceǁget_severity_definitions__mutmut_70(self) -> list[SeverityDefinition]:
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
                priority=None,
                min_score=self.high_max + 1,
                max_score=100,
            ),
        ]

    def xǁSeverityServiceǁget_severity_definitions__mutmut_71(self) -> list[SeverityDefinition]:
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
                min_score=None,
                max_score=100,
            ),
        ]

    def xǁSeverityServiceǁget_severity_definitions__mutmut_72(self) -> list[SeverityDefinition]:
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
                max_score=None,
            ),
        ]

    def xǁSeverityServiceǁget_severity_definitions__mutmut_73(self) -> list[SeverityDefinition]:
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
                label="Critical",
                description="Immediate attention required",
                color=SEVERITY_COLORS[Severity.CRITICAL],
                priority=SEVERITY_PRIORITY[Severity.CRITICAL],
                min_score=self.high_max + 1,
                max_score=100,
            ),
        ]

    def xǁSeverityServiceǁget_severity_definitions__mutmut_74(self) -> list[SeverityDefinition]:
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
                description="Immediate attention required",
                color=SEVERITY_COLORS[Severity.CRITICAL],
                priority=SEVERITY_PRIORITY[Severity.CRITICAL],
                min_score=self.high_max + 1,
                max_score=100,
            ),
        ]

    def xǁSeverityServiceǁget_severity_definitions__mutmut_75(self) -> list[SeverityDefinition]:
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
                color=SEVERITY_COLORS[Severity.CRITICAL],
                priority=SEVERITY_PRIORITY[Severity.CRITICAL],
                min_score=self.high_max + 1,
                max_score=100,
            ),
        ]

    def xǁSeverityServiceǁget_severity_definitions__mutmut_76(self) -> list[SeverityDefinition]:
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
                priority=SEVERITY_PRIORITY[Severity.CRITICAL],
                min_score=self.high_max + 1,
                max_score=100,
            ),
        ]

    def xǁSeverityServiceǁget_severity_definitions__mutmut_77(self) -> list[SeverityDefinition]:
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
                min_score=self.high_max + 1,
                max_score=100,
            ),
        ]

    def xǁSeverityServiceǁget_severity_definitions__mutmut_78(self) -> list[SeverityDefinition]:
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
                max_score=100,
            ),
        ]

    def xǁSeverityServiceǁget_severity_definitions__mutmut_79(self) -> list[SeverityDefinition]:
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
            ),
        ]

    def xǁSeverityServiceǁget_severity_definitions__mutmut_80(self) -> list[SeverityDefinition]:
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
                label="XXCriticalXX",
                description="Immediate attention required",
                color=SEVERITY_COLORS[Severity.CRITICAL],
                priority=SEVERITY_PRIORITY[Severity.CRITICAL],
                min_score=self.high_max + 1,
                max_score=100,
            ),
        ]

    def xǁSeverityServiceǁget_severity_definitions__mutmut_81(self) -> list[SeverityDefinition]:
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
                label="critical",
                description="Immediate attention required",
                color=SEVERITY_COLORS[Severity.CRITICAL],
                priority=SEVERITY_PRIORITY[Severity.CRITICAL],
                min_score=self.high_max + 1,
                max_score=100,
            ),
        ]

    def xǁSeverityServiceǁget_severity_definitions__mutmut_82(self) -> list[SeverityDefinition]:
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
                label="CRITICAL",
                description="Immediate attention required",
                color=SEVERITY_COLORS[Severity.CRITICAL],
                priority=SEVERITY_PRIORITY[Severity.CRITICAL],
                min_score=self.high_max + 1,
                max_score=100,
            ),
        ]

    def xǁSeverityServiceǁget_severity_definitions__mutmut_83(self) -> list[SeverityDefinition]:
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
                description="XXImmediate attention requiredXX",
                color=SEVERITY_COLORS[Severity.CRITICAL],
                priority=SEVERITY_PRIORITY[Severity.CRITICAL],
                min_score=self.high_max + 1,
                max_score=100,
            ),
        ]

    def xǁSeverityServiceǁget_severity_definitions__mutmut_84(self) -> list[SeverityDefinition]:
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
                description="immediate attention required",
                color=SEVERITY_COLORS[Severity.CRITICAL],
                priority=SEVERITY_PRIORITY[Severity.CRITICAL],
                min_score=self.high_max + 1,
                max_score=100,
            ),
        ]

    def xǁSeverityServiceǁget_severity_definitions__mutmut_85(self) -> list[SeverityDefinition]:
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
                description="IMMEDIATE ATTENTION REQUIRED",
                color=SEVERITY_COLORS[Severity.CRITICAL],
                priority=SEVERITY_PRIORITY[Severity.CRITICAL],
                min_score=self.high_max + 1,
                max_score=100,
            ),
        ]

    def xǁSeverityServiceǁget_severity_definitions__mutmut_86(self) -> list[SeverityDefinition]:
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
                min_score=self.high_max - 1,
                max_score=100,
            ),
        ]

    def xǁSeverityServiceǁget_severity_definitions__mutmut_87(self) -> list[SeverityDefinition]:
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
                min_score=self.high_max + 2,
                max_score=100,
            ),
        ]

    def xǁSeverityServiceǁget_severity_definitions__mutmut_88(self) -> list[SeverityDefinition]:
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
                max_score=101,
            ),
        ]

    xǁSeverityServiceǁget_severity_definitions__mutmut_mutants: ClassVar[MutantDict] = {
        "xǁSeverityServiceǁget_severity_definitions__mutmut_1": xǁSeverityServiceǁget_severity_definitions__mutmut_1,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_2": xǁSeverityServiceǁget_severity_definitions__mutmut_2,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_3": xǁSeverityServiceǁget_severity_definitions__mutmut_3,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_4": xǁSeverityServiceǁget_severity_definitions__mutmut_4,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_5": xǁSeverityServiceǁget_severity_definitions__mutmut_5,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_6": xǁSeverityServiceǁget_severity_definitions__mutmut_6,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_7": xǁSeverityServiceǁget_severity_definitions__mutmut_7,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_8": xǁSeverityServiceǁget_severity_definitions__mutmut_8,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_9": xǁSeverityServiceǁget_severity_definitions__mutmut_9,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_10": xǁSeverityServiceǁget_severity_definitions__mutmut_10,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_11": xǁSeverityServiceǁget_severity_definitions__mutmut_11,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_12": xǁSeverityServiceǁget_severity_definitions__mutmut_12,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_13": xǁSeverityServiceǁget_severity_definitions__mutmut_13,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_14": xǁSeverityServiceǁget_severity_definitions__mutmut_14,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_15": xǁSeverityServiceǁget_severity_definitions__mutmut_15,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_16": xǁSeverityServiceǁget_severity_definitions__mutmut_16,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_17": xǁSeverityServiceǁget_severity_definitions__mutmut_17,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_18": xǁSeverityServiceǁget_severity_definitions__mutmut_18,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_19": xǁSeverityServiceǁget_severity_definitions__mutmut_19,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_20": xǁSeverityServiceǁget_severity_definitions__mutmut_20,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_21": xǁSeverityServiceǁget_severity_definitions__mutmut_21,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_22": xǁSeverityServiceǁget_severity_definitions__mutmut_22,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_23": xǁSeverityServiceǁget_severity_definitions__mutmut_23,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_24": xǁSeverityServiceǁget_severity_definitions__mutmut_24,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_25": xǁSeverityServiceǁget_severity_definitions__mutmut_25,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_26": xǁSeverityServiceǁget_severity_definitions__mutmut_26,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_27": xǁSeverityServiceǁget_severity_definitions__mutmut_27,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_28": xǁSeverityServiceǁget_severity_definitions__mutmut_28,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_29": xǁSeverityServiceǁget_severity_definitions__mutmut_29,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_30": xǁSeverityServiceǁget_severity_definitions__mutmut_30,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_31": xǁSeverityServiceǁget_severity_definitions__mutmut_31,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_32": xǁSeverityServiceǁget_severity_definitions__mutmut_32,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_33": xǁSeverityServiceǁget_severity_definitions__mutmut_33,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_34": xǁSeverityServiceǁget_severity_definitions__mutmut_34,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_35": xǁSeverityServiceǁget_severity_definitions__mutmut_35,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_36": xǁSeverityServiceǁget_severity_definitions__mutmut_36,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_37": xǁSeverityServiceǁget_severity_definitions__mutmut_37,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_38": xǁSeverityServiceǁget_severity_definitions__mutmut_38,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_39": xǁSeverityServiceǁget_severity_definitions__mutmut_39,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_40": xǁSeverityServiceǁget_severity_definitions__mutmut_40,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_41": xǁSeverityServiceǁget_severity_definitions__mutmut_41,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_42": xǁSeverityServiceǁget_severity_definitions__mutmut_42,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_43": xǁSeverityServiceǁget_severity_definitions__mutmut_43,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_44": xǁSeverityServiceǁget_severity_definitions__mutmut_44,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_45": xǁSeverityServiceǁget_severity_definitions__mutmut_45,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_46": xǁSeverityServiceǁget_severity_definitions__mutmut_46,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_47": xǁSeverityServiceǁget_severity_definitions__mutmut_47,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_48": xǁSeverityServiceǁget_severity_definitions__mutmut_48,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_49": xǁSeverityServiceǁget_severity_definitions__mutmut_49,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_50": xǁSeverityServiceǁget_severity_definitions__mutmut_50,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_51": xǁSeverityServiceǁget_severity_definitions__mutmut_51,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_52": xǁSeverityServiceǁget_severity_definitions__mutmut_52,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_53": xǁSeverityServiceǁget_severity_definitions__mutmut_53,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_54": xǁSeverityServiceǁget_severity_definitions__mutmut_54,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_55": xǁSeverityServiceǁget_severity_definitions__mutmut_55,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_56": xǁSeverityServiceǁget_severity_definitions__mutmut_56,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_57": xǁSeverityServiceǁget_severity_definitions__mutmut_57,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_58": xǁSeverityServiceǁget_severity_definitions__mutmut_58,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_59": xǁSeverityServiceǁget_severity_definitions__mutmut_59,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_60": xǁSeverityServiceǁget_severity_definitions__mutmut_60,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_61": xǁSeverityServiceǁget_severity_definitions__mutmut_61,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_62": xǁSeverityServiceǁget_severity_definitions__mutmut_62,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_63": xǁSeverityServiceǁget_severity_definitions__mutmut_63,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_64": xǁSeverityServiceǁget_severity_definitions__mutmut_64,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_65": xǁSeverityServiceǁget_severity_definitions__mutmut_65,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_66": xǁSeverityServiceǁget_severity_definitions__mutmut_66,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_67": xǁSeverityServiceǁget_severity_definitions__mutmut_67,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_68": xǁSeverityServiceǁget_severity_definitions__mutmut_68,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_69": xǁSeverityServiceǁget_severity_definitions__mutmut_69,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_70": xǁSeverityServiceǁget_severity_definitions__mutmut_70,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_71": xǁSeverityServiceǁget_severity_definitions__mutmut_71,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_72": xǁSeverityServiceǁget_severity_definitions__mutmut_72,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_73": xǁSeverityServiceǁget_severity_definitions__mutmut_73,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_74": xǁSeverityServiceǁget_severity_definitions__mutmut_74,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_75": xǁSeverityServiceǁget_severity_definitions__mutmut_75,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_76": xǁSeverityServiceǁget_severity_definitions__mutmut_76,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_77": xǁSeverityServiceǁget_severity_definitions__mutmut_77,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_78": xǁSeverityServiceǁget_severity_definitions__mutmut_78,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_79": xǁSeverityServiceǁget_severity_definitions__mutmut_79,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_80": xǁSeverityServiceǁget_severity_definitions__mutmut_80,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_81": xǁSeverityServiceǁget_severity_definitions__mutmut_81,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_82": xǁSeverityServiceǁget_severity_definitions__mutmut_82,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_83": xǁSeverityServiceǁget_severity_definitions__mutmut_83,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_84": xǁSeverityServiceǁget_severity_definitions__mutmut_84,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_85": xǁSeverityServiceǁget_severity_definitions__mutmut_85,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_86": xǁSeverityServiceǁget_severity_definitions__mutmut_86,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_87": xǁSeverityServiceǁget_severity_definitions__mutmut_87,
        "xǁSeverityServiceǁget_severity_definitions__mutmut_88": xǁSeverityServiceǁget_severity_definitions__mutmut_88,
    }

    def get_severity_definitions(self, *args, **kwargs):
        result = _mutmut_trampoline(
            object.__getattribute__(
                self, "xǁSeverityServiceǁget_severity_definitions__mutmut_orig"
            ),
            object.__getattribute__(
                self, "xǁSeverityServiceǁget_severity_definitions__mutmut_mutants"
            ),
            args,
            kwargs,
            self,
        )
        return result

    get_severity_definitions.__signature__ = _mutmut_signature(
        xǁSeverityServiceǁget_severity_definitions__mutmut_orig
    )
    xǁSeverityServiceǁget_severity_definitions__mutmut_orig.__name__ = (
        "xǁSeverityServiceǁget_severity_definitions"
    )

    def xǁSeverityServiceǁget_thresholds__mutmut_orig(self) -> dict[str, int]:
        """Get current severity thresholds.

        Returns:
            Dictionary with threshold values
        """
        return {
            "low_max": self.low_max,
            "medium_max": self.medium_max,
            "high_max": self.high_max,
        }

    def xǁSeverityServiceǁget_thresholds__mutmut_1(self) -> dict[str, int]:
        """Get current severity thresholds.

        Returns:
            Dictionary with threshold values
        """
        return {
            "XXlow_maxXX": self.low_max,
            "medium_max": self.medium_max,
            "high_max": self.high_max,
        }

    def xǁSeverityServiceǁget_thresholds__mutmut_2(self) -> dict[str, int]:
        """Get current severity thresholds.

        Returns:
            Dictionary with threshold values
        """
        return {
            "LOW_MAX": self.low_max,
            "medium_max": self.medium_max,
            "high_max": self.high_max,
        }

    def xǁSeverityServiceǁget_thresholds__mutmut_3(self) -> dict[str, int]:
        """Get current severity thresholds.

        Returns:
            Dictionary with threshold values
        """
        return {
            "low_max": self.low_max,
            "XXmedium_maxXX": self.medium_max,
            "high_max": self.high_max,
        }

    def xǁSeverityServiceǁget_thresholds__mutmut_4(self) -> dict[str, int]:
        """Get current severity thresholds.

        Returns:
            Dictionary with threshold values
        """
        return {
            "low_max": self.low_max,
            "MEDIUM_MAX": self.medium_max,
            "high_max": self.high_max,
        }

    def xǁSeverityServiceǁget_thresholds__mutmut_5(self) -> dict[str, int]:
        """Get current severity thresholds.

        Returns:
            Dictionary with threshold values
        """
        return {
            "low_max": self.low_max,
            "medium_max": self.medium_max,
            "XXhigh_maxXX": self.high_max,
        }

    def xǁSeverityServiceǁget_thresholds__mutmut_6(self) -> dict[str, int]:
        """Get current severity thresholds.

        Returns:
            Dictionary with threshold values
        """
        return {
            "low_max": self.low_max,
            "medium_max": self.medium_max,
            "HIGH_MAX": self.high_max,
        }

    xǁSeverityServiceǁget_thresholds__mutmut_mutants: ClassVar[MutantDict] = {
        "xǁSeverityServiceǁget_thresholds__mutmut_1": xǁSeverityServiceǁget_thresholds__mutmut_1,
        "xǁSeverityServiceǁget_thresholds__mutmut_2": xǁSeverityServiceǁget_thresholds__mutmut_2,
        "xǁSeverityServiceǁget_thresholds__mutmut_3": xǁSeverityServiceǁget_thresholds__mutmut_3,
        "xǁSeverityServiceǁget_thresholds__mutmut_4": xǁSeverityServiceǁget_thresholds__mutmut_4,
        "xǁSeverityServiceǁget_thresholds__mutmut_5": xǁSeverityServiceǁget_thresholds__mutmut_5,
        "xǁSeverityServiceǁget_thresholds__mutmut_6": xǁSeverityServiceǁget_thresholds__mutmut_6,
    }

    def get_thresholds(self, *args, **kwargs):
        result = _mutmut_trampoline(
            object.__getattribute__(self, "xǁSeverityServiceǁget_thresholds__mutmut_orig"),
            object.__getattribute__(self, "xǁSeverityServiceǁget_thresholds__mutmut_mutants"),
            args,
            kwargs,
            self,
        )
        return result

    get_thresholds.__signature__ = _mutmut_signature(xǁSeverityServiceǁget_thresholds__mutmut_orig)
    xǁSeverityServiceǁget_thresholds__mutmut_orig.__name__ = "xǁSeverityServiceǁget_thresholds"


# =============================================================================
# Utility Functions
# =============================================================================


def x_get_severity_color__mutmut_orig(severity: Severity) -> str:
    """Get the hex color code for a severity level.

    Args:
        severity: The severity level

    Returns:
        Hex color code (e.g., "#22c55e")
    """
    return SEVERITY_COLORS.get(severity, SEVERITY_COLORS[Severity.LOW])


# =============================================================================
# Utility Functions
# =============================================================================


def x_get_severity_color__mutmut_1(severity: Severity) -> str:
    """Get the hex color code for a severity level.

    Args:
        severity: The severity level

    Returns:
        Hex color code (e.g., "#22c55e")
    """
    return SEVERITY_COLORS.get(None, SEVERITY_COLORS[Severity.LOW])


# =============================================================================
# Utility Functions
# =============================================================================


def x_get_severity_color__mutmut_2(severity: Severity) -> str:
    """Get the hex color code for a severity level.

    Args:
        severity: The severity level

    Returns:
        Hex color code (e.g., "#22c55e")
    """
    return SEVERITY_COLORS.get(severity)


# =============================================================================
# Utility Functions
# =============================================================================


def x_get_severity_color__mutmut_3(severity: Severity) -> str:
    """Get the hex color code for a severity level.

    Args:
        severity: The severity level

    Returns:
        Hex color code (e.g., "#22c55e")
    """
    return SEVERITY_COLORS.get(SEVERITY_COLORS[Severity.LOW])


# =============================================================================
# Utility Functions
# =============================================================================


def x_get_severity_color__mutmut_4(severity: Severity) -> str:
    """Get the hex color code for a severity level.

    Args:
        severity: The severity level

    Returns:
        Hex color code (e.g., "#22c55e")
    """
    return SEVERITY_COLORS.get(
        severity,
    )


x_get_severity_color__mutmut_mutants: ClassVar[MutantDict] = {
    "x_get_severity_color__mutmut_1": x_get_severity_color__mutmut_1,
    "x_get_severity_color__mutmut_2": x_get_severity_color__mutmut_2,
    "x_get_severity_color__mutmut_3": x_get_severity_color__mutmut_3,
    "x_get_severity_color__mutmut_4": x_get_severity_color__mutmut_4,
}


def get_severity_color(*args, **kwargs):
    result = _mutmut_trampoline(
        x_get_severity_color__mutmut_orig, x_get_severity_color__mutmut_mutants, args, kwargs
    )
    return result


get_severity_color.__signature__ = _mutmut_signature(x_get_severity_color__mutmut_orig)
x_get_severity_color__mutmut_orig.__name__ = "x_get_severity_color"


def x_get_severity_priority__mutmut_orig(severity: Severity) -> int:
    """Get the sort priority for a severity level.

    Lower values indicate higher priority (critical=0, low=3).

    Args:
        severity: The severity level

    Returns:
        Sort priority as integer (0 = highest priority)
    """
    return SEVERITY_PRIORITY.get(severity, SEVERITY_PRIORITY[Severity.LOW])


def x_get_severity_priority__mutmut_1(severity: Severity) -> int:
    """Get the sort priority for a severity level.

    Lower values indicate higher priority (critical=0, low=3).

    Args:
        severity: The severity level

    Returns:
        Sort priority as integer (0 = highest priority)
    """
    return SEVERITY_PRIORITY.get(None, SEVERITY_PRIORITY[Severity.LOW])


def x_get_severity_priority__mutmut_2(severity: Severity) -> int:
    """Get the sort priority for a severity level.

    Lower values indicate higher priority (critical=0, low=3).

    Args:
        severity: The severity level

    Returns:
        Sort priority as integer (0 = highest priority)
    """
    return SEVERITY_PRIORITY.get(severity)


def x_get_severity_priority__mutmut_3(severity: Severity) -> int:
    """Get the sort priority for a severity level.

    Lower values indicate higher priority (critical=0, low=3).

    Args:
        severity: The severity level

    Returns:
        Sort priority as integer (0 = highest priority)
    """
    return SEVERITY_PRIORITY.get(SEVERITY_PRIORITY[Severity.LOW])


def x_get_severity_priority__mutmut_4(severity: Severity) -> int:
    """Get the sort priority for a severity level.

    Lower values indicate higher priority (critical=0, low=3).

    Args:
        severity: The severity level

    Returns:
        Sort priority as integer (0 = highest priority)
    """
    return SEVERITY_PRIORITY.get(
        severity,
    )


x_get_severity_priority__mutmut_mutants: ClassVar[MutantDict] = {
    "x_get_severity_priority__mutmut_1": x_get_severity_priority__mutmut_1,
    "x_get_severity_priority__mutmut_2": x_get_severity_priority__mutmut_2,
    "x_get_severity_priority__mutmut_3": x_get_severity_priority__mutmut_3,
    "x_get_severity_priority__mutmut_4": x_get_severity_priority__mutmut_4,
}


def get_severity_priority(*args, **kwargs):
    result = _mutmut_trampoline(
        x_get_severity_priority__mutmut_orig, x_get_severity_priority__mutmut_mutants, args, kwargs
    )
    return result


get_severity_priority.__signature__ = _mutmut_signature(x_get_severity_priority__mutmut_orig)
x_get_severity_priority__mutmut_orig.__name__ = "x_get_severity_priority"


def x_severity_gte__mutmut_orig(a: Severity, b: Severity) -> bool:
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


def x_severity_gte__mutmut_1(a: Severity, b: Severity) -> bool:
    """Check if severity a is greater than or equal to severity b.

    "Greater" means more severe (critical > high > medium > low).

    Args:
        a: First severity level
        b: Second severity level

    Returns:
        True if a is at least as severe as b
    """
    # Lower priority number = higher severity
    return get_severity_priority(None) <= get_severity_priority(b)


def x_severity_gte__mutmut_2(a: Severity, b: Severity) -> bool:
    """Check if severity a is greater than or equal to severity b.

    "Greater" means more severe (critical > high > medium > low).

    Args:
        a: First severity level
        b: Second severity level

    Returns:
        True if a is at least as severe as b
    """
    # Lower priority number = higher severity
    return get_severity_priority(a) < get_severity_priority(b)


def x_severity_gte__mutmut_3(a: Severity, b: Severity) -> bool:
    """Check if severity a is greater than or equal to severity b.

    "Greater" means more severe (critical > high > medium > low).

    Args:
        a: First severity level
        b: Second severity level

    Returns:
        True if a is at least as severe as b
    """
    # Lower priority number = higher severity
    return get_severity_priority(a) <= get_severity_priority(None)


x_severity_gte__mutmut_mutants: ClassVar[MutantDict] = {
    "x_severity_gte__mutmut_1": x_severity_gte__mutmut_1,
    "x_severity_gte__mutmut_2": x_severity_gte__mutmut_2,
    "x_severity_gte__mutmut_3": x_severity_gte__mutmut_3,
}


def severity_gte(*args, **kwargs):
    result = _mutmut_trampoline(
        x_severity_gte__mutmut_orig, x_severity_gte__mutmut_mutants, args, kwargs
    )
    return result


severity_gte.__signature__ = _mutmut_signature(x_severity_gte__mutmut_orig)
x_severity_gte__mutmut_orig.__name__ = "x_severity_gte"


def x_severity_gt__mutmut_orig(a: Severity, b: Severity) -> bool:
    """Check if severity a is strictly greater than severity b.

    "Greater" means more severe (critical > high > medium > low).

    Args:
        a: First severity level
        b: Second severity level

    Returns:
        True if a is more severe than b
    """
    return get_severity_priority(a) < get_severity_priority(b)


def x_severity_gt__mutmut_1(a: Severity, b: Severity) -> bool:
    """Check if severity a is strictly greater than severity b.

    "Greater" means more severe (critical > high > medium > low).

    Args:
        a: First severity level
        b: Second severity level

    Returns:
        True if a is more severe than b
    """
    return get_severity_priority(None) < get_severity_priority(b)


def x_severity_gt__mutmut_2(a: Severity, b: Severity) -> bool:
    """Check if severity a is strictly greater than severity b.

    "Greater" means more severe (critical > high > medium > low).

    Args:
        a: First severity level
        b: Second severity level

    Returns:
        True if a is more severe than b
    """
    return get_severity_priority(a) <= get_severity_priority(b)


def x_severity_gt__mutmut_3(a: Severity, b: Severity) -> bool:
    """Check if severity a is strictly greater than severity b.

    "Greater" means more severe (critical > high > medium > low).

    Args:
        a: First severity level
        b: Second severity level

    Returns:
        True if a is more severe than b
    """
    return get_severity_priority(a) < get_severity_priority(None)


x_severity_gt__mutmut_mutants: ClassVar[MutantDict] = {
    "x_severity_gt__mutmut_1": x_severity_gt__mutmut_1,
    "x_severity_gt__mutmut_2": x_severity_gt__mutmut_2,
    "x_severity_gt__mutmut_3": x_severity_gt__mutmut_3,
}


def severity_gt(*args, **kwargs):
    result = _mutmut_trampoline(
        x_severity_gt__mutmut_orig, x_severity_gt__mutmut_mutants, args, kwargs
    )
    return result


severity_gt.__signature__ = _mutmut_signature(x_severity_gt__mutmut_orig)
x_severity_gt__mutmut_orig.__name__ = "x_severity_gt"


def x_severity_lte__mutmut_orig(a: Severity, b: Severity) -> bool:
    """Check if severity a is less than or equal to severity b.

    "Less" means less severe (low < medium < high < critical).

    Args:
        a: First severity level
        b: Second severity level

    Returns:
        True if a is at most as severe as b
    """
    return get_severity_priority(a) >= get_severity_priority(b)


def x_severity_lte__mutmut_1(a: Severity, b: Severity) -> bool:
    """Check if severity a is less than or equal to severity b.

    "Less" means less severe (low < medium < high < critical).

    Args:
        a: First severity level
        b: Second severity level

    Returns:
        True if a is at most as severe as b
    """
    return get_severity_priority(None) >= get_severity_priority(b)


def x_severity_lte__mutmut_2(a: Severity, b: Severity) -> bool:
    """Check if severity a is less than or equal to severity b.

    "Less" means less severe (low < medium < high < critical).

    Args:
        a: First severity level
        b: Second severity level

    Returns:
        True if a is at most as severe as b
    """
    return get_severity_priority(a) > get_severity_priority(b)


def x_severity_lte__mutmut_3(a: Severity, b: Severity) -> bool:
    """Check if severity a is less than or equal to severity b.

    "Less" means less severe (low < medium < high < critical).

    Args:
        a: First severity level
        b: Second severity level

    Returns:
        True if a is at most as severe as b
    """
    return get_severity_priority(a) >= get_severity_priority(None)


x_severity_lte__mutmut_mutants: ClassVar[MutantDict] = {
    "x_severity_lte__mutmut_1": x_severity_lte__mutmut_1,
    "x_severity_lte__mutmut_2": x_severity_lte__mutmut_2,
    "x_severity_lte__mutmut_3": x_severity_lte__mutmut_3,
}


def severity_lte(*args, **kwargs):
    result = _mutmut_trampoline(
        x_severity_lte__mutmut_orig, x_severity_lte__mutmut_mutants, args, kwargs
    )
    return result


severity_lte.__signature__ = _mutmut_signature(x_severity_lte__mutmut_orig)
x_severity_lte__mutmut_orig.__name__ = "x_severity_lte"


def x_severity_lt__mutmut_orig(a: Severity, b: Severity) -> bool:
    """Check if severity a is strictly less than severity b.

    "Less" means less severe (low < medium < high < critical).

    Args:
        a: First severity level
        b: Second severity level

    Returns:
        True if a is less severe than b
    """
    return get_severity_priority(a) > get_severity_priority(b)


def x_severity_lt__mutmut_1(a: Severity, b: Severity) -> bool:
    """Check if severity a is strictly less than severity b.

    "Less" means less severe (low < medium < high < critical).

    Args:
        a: First severity level
        b: Second severity level

    Returns:
        True if a is less severe than b
    """
    return get_severity_priority(None) > get_severity_priority(b)


def x_severity_lt__mutmut_2(a: Severity, b: Severity) -> bool:
    """Check if severity a is strictly less than severity b.

    "Less" means less severe (low < medium < high < critical).

    Args:
        a: First severity level
        b: Second severity level

    Returns:
        True if a is less severe than b
    """
    return get_severity_priority(a) >= get_severity_priority(b)


def x_severity_lt__mutmut_3(a: Severity, b: Severity) -> bool:
    """Check if severity a is strictly less than severity b.

    "Less" means less severe (low < medium < high < critical).

    Args:
        a: First severity level
        b: Second severity level

    Returns:
        True if a is less severe than b
    """
    return get_severity_priority(a) > get_severity_priority(None)


x_severity_lt__mutmut_mutants: ClassVar[MutantDict] = {
    "x_severity_lt__mutmut_1": x_severity_lt__mutmut_1,
    "x_severity_lt__mutmut_2": x_severity_lt__mutmut_2,
    "x_severity_lt__mutmut_3": x_severity_lt__mutmut_3,
}


def severity_lt(*args, **kwargs):
    result = _mutmut_trampoline(
        x_severity_lt__mutmut_orig, x_severity_lt__mutmut_mutants, args, kwargs
    )
    return result


severity_lt.__signature__ = _mutmut_signature(x_severity_lt__mutmut_orig)
x_severity_lt__mutmut_orig.__name__ = "x_severity_lt"


def x_severity_from_string__mutmut_orig(value: str) -> Severity:
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


def x_severity_from_string__mutmut_1(value: str) -> Severity:
    """Convert a string to a Severity enum value.

    Args:
        value: String representation of severity (case-insensitive)

    Returns:
        Corresponding Severity enum value

    Raises:
        ValueError: If the string doesn't match any severity level
    """
    try:
        return Severity(None)
    except ValueError as e:
        valid_values = [s.value for s in Severity]
        raise ValueError(
            f"Invalid severity value: {value!r}. Must be one of: {valid_values}"
        ) from e


def x_severity_from_string__mutmut_2(value: str) -> Severity:
    """Convert a string to a Severity enum value.

    Args:
        value: String representation of severity (case-insensitive)

    Returns:
        Corresponding Severity enum value

    Raises:
        ValueError: If the string doesn't match any severity level
    """
    try:
        return Severity(value.upper())
    except ValueError as e:
        valid_values = [s.value for s in Severity]
        raise ValueError(
            f"Invalid severity value: {value!r}. Must be one of: {valid_values}"
        ) from e


def x_severity_from_string__mutmut_3(value: str) -> Severity:
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
        valid_values = None
        raise ValueError(
            f"Invalid severity value: {value!r}. Must be one of: {valid_values}"
        ) from e


def x_severity_from_string__mutmut_4(value: str) -> Severity:
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
        raise ValueError(None) from e


x_severity_from_string__mutmut_mutants: ClassVar[MutantDict] = {
    "x_severity_from_string__mutmut_1": x_severity_from_string__mutmut_1,
    "x_severity_from_string__mutmut_2": x_severity_from_string__mutmut_2,
    "x_severity_from_string__mutmut_3": x_severity_from_string__mutmut_3,
    "x_severity_from_string__mutmut_4": x_severity_from_string__mutmut_4,
}


def severity_from_string(*args, **kwargs):
    result = _mutmut_trampoline(
        x_severity_from_string__mutmut_orig, x_severity_from_string__mutmut_mutants, args, kwargs
    )
    return result


severity_from_string.__signature__ = _mutmut_signature(x_severity_from_string__mutmut_orig)
x_severity_from_string__mutmut_orig.__name__ = "x_severity_from_string"


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
