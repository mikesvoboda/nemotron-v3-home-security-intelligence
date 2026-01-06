"""Pydantic schemas for LLM response validation.

This module defines schemas for validating and normalizing responses from the
Nemotron LLM service. The schemas provide type-safe parsing and validation
of risk assessment data returned by the LLM.

Schemas:
    LLMRiskResponse: Validated risk assessment with strict constraints
    LLMRawResponse: Lenient parsing for raw LLM JSON output
    RiskLevel: Enum of valid risk level values
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RiskLevel(str, Enum):
    """Valid risk levels for security event assessment.

    These levels correspond to the backend severity taxonomy:
    - LOW: 0-29 - Routine activity, no concern
    - MEDIUM: 30-59 - Notable activity, worth reviewing
    - HIGH: 60-84 - Concerning activity, review soon
    - CRITICAL: 85-100 - Immediate attention required
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    def __str__(self) -> str:
        """Return string representation of risk level."""
        return self.value


# Default severity thresholds (matches backend.services.severity)
DEFAULT_LOW_MAX = 29
DEFAULT_MEDIUM_MAX = 59
DEFAULT_HIGH_MAX = 84


def infer_risk_level_from_score(score: int) -> RiskLevel:
    """Infer risk level from score using default thresholds.

    Args:
        score: Risk score (0-100)

    Returns:
        Inferred RiskLevel based on score thresholds
    """
    if score <= DEFAULT_LOW_MAX:
        return RiskLevel.LOW
    elif score <= DEFAULT_MEDIUM_MAX:
        return RiskLevel.MEDIUM
    elif score <= DEFAULT_HIGH_MAX:
        return RiskLevel.HIGH
    else:
        return RiskLevel.CRITICAL


class LLMRiskResponse(BaseModel):
    """Validated risk assessment response from Nemotron LLM.

    This schema enforces strict validation rules:
    - risk_score must be an integer between 0 and 100
    - risk_level must be a valid RiskLevel enum value
    - summary and reasoning are required strings

    This schema should be used after raw LLM JSON has been parsed
    and normalized (e.g., via LLMRawResponse.to_validated_response()).

    Attributes:
        risk_score: Risk assessment score (0-100)
        risk_level: Risk classification level
        summary: Human-readable event summary
        reasoning: Detailed reasoning for the risk assessment
    """

    model_config = ConfigDict(
        extra="ignore",  # Ignore extra fields from LLM output
        json_schema_extra={
            "example": {
                "risk_score": 75,
                "risk_level": "high",
                "summary": "Suspicious activity detected at front entrance",
                "reasoning": "Person detected at unusual time with unknown vehicle",
            }
        },
    )

    risk_score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Risk assessment score (0-100)",
    )
    risk_level: str = Field(
        ...,
        description="Risk classification level (low, medium, high, critical)",
    )
    summary: str = Field(
        ...,
        description="Human-readable event summary",
    )
    reasoning: str = Field(
        ...,
        description="Detailed reasoning for the risk assessment",
    )

    @field_validator("risk_score", mode="before")
    @classmethod
    def coerce_risk_score(cls, v: Any) -> int:
        """Coerce risk_score to integer.

        Handles string numbers and floats from LLM output.

        Args:
            v: Raw risk_score value

        Returns:
            Integer risk score

        Raises:
            ValueError: If value cannot be converted to integer
        """
        if v is None:
            raise ValueError("risk_score is required")
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return int(v)
        if isinstance(v, str):
            try:
                return int(float(v))
            except ValueError:
                raise ValueError(f"Cannot convert '{v}' to integer") from None
        raise ValueError(f"risk_score must be numeric, got {type(v).__name__}")

    @field_validator("risk_level", mode="before")
    @classmethod
    def validate_risk_level(cls, v: str | RiskLevel) -> str:
        """Validate and normalize risk_level.

        Accepts string values and normalizes to lowercase.

        Args:
            v: Raw risk_level value

        Returns:
            Normalized lowercase risk level string

        Raises:
            ValueError: If value is not a valid risk level
        """
        if isinstance(v, RiskLevel):
            return v.value

        if isinstance(v, str):
            normalized = v.lower()
            valid_values = [level.value for level in RiskLevel]
            if normalized in valid_values:
                return normalized
            raise ValueError(f"Invalid risk_level '{v}'. Must be one of: {valid_values}")

        raise ValueError(f"risk_level must be a string, got {type(v).__name__}")


class LLMRawResponse(BaseModel):
    """Lenient schema for parsing raw LLM JSON output.

    This schema provides minimal validation to handle potentially
    malformed LLM responses. It allows:
    - risk_score outside 0-100 range (clamped during validation)
    - Invalid risk_level values (inferred from score during validation)
    - Missing summary/reasoning (defaults provided during validation)

    Use the to_validated_response() method to convert to a strictly
    validated LLMRiskResponse.

    Attributes:
        risk_score: Raw risk score (may be out of range)
        risk_level: Raw risk level string (may be invalid)
        summary: Optional event summary
        reasoning: Optional reasoning text
    """

    model_config = ConfigDict(
        extra="ignore",  # Ignore extra fields from LLM
        json_schema_extra={
            "example": {
                "risk_score": 150,
                "risk_level": "EXTREME",
                "summary": "Test",
                "reasoning": "Test",
            }
        },
    )

    risk_score: int | float | None = Field(
        ...,
        description="Raw risk score from LLM (may be out of range)",
    )
    risk_level: str = Field(
        ...,
        description="Raw risk level string from LLM (may be invalid)",
    )
    summary: str | None = Field(
        None,
        description="Event summary (optional in raw response)",
    )
    reasoning: str | None = Field(
        None,
        description="Reasoning text (optional in raw response)",
    )

    @model_validator(mode="before")
    @classmethod
    def validate_required_fields(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Ensure risk_score and risk_level are present.

        Args:
            data: Raw input data

        Returns:
            Validated data

        Raises:
            ValueError: If required fields are missing
        """
        if not isinstance(data, dict):
            raise ValueError("Input must be a dictionary")

        if "risk_score" not in data and "risk_level" not in data:
            raise ValueError("Missing required fields: risk_score and risk_level")
        if "risk_score" not in data:
            raise ValueError("Missing required field: risk_score")
        if "risk_level" not in data:
            raise ValueError("Missing required field: risk_level")

        return data

    def to_validated_response(self) -> LLMRiskResponse:
        """Convert raw response to validated LLMRiskResponse.

        This method:
        1. Clamps risk_score to 0-100 range
        2. Normalizes risk_level to lowercase
        3. Infers risk_level from score if invalid
        4. Provides defaults for missing summary/reasoning

        Returns:
            Validated LLMRiskResponse instance
        """
        # Handle None or invalid risk_score
        if self.risk_score is None:
            score = 50  # Default
        else:
            try:
                score = int(self.risk_score)
            except (ValueError, TypeError):
                score = 50  # Default on conversion failure

        # Clamp to valid range
        score = max(0, min(100, score))

        # Validate and normalize risk_level
        valid_levels = {level.value for level in RiskLevel}
        normalized_level = self.risk_level.lower() if self.risk_level else ""

        if normalized_level not in valid_levels:
            # Infer from score
            inferred = infer_risk_level_from_score(score)
            normalized_level = inferred.value

        # Provide defaults for optional fields
        summary = self.summary if self.summary else "Risk analysis completed"
        reasoning = self.reasoning if self.reasoning else "No detailed reasoning provided"

        return LLMRiskResponse(
            risk_score=score,
            risk_level=normalized_level,
            summary=summary,
            reasoning=reasoning,
        )
