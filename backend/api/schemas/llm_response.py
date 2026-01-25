"""Pydantic schemas for LLM response validation.

This module defines schemas for validating and normalizing responses from the
Nemotron LLM service. The schemas provide type-safe parsing and validation
of risk assessment data returned by the LLM.

Schemas:
    LLMRiskResponse: Validated risk assessment with strict constraints
    LLMRawResponse: Lenient parsing for raw LLM JSON output
    RiskLevel: Enum of valid risk level values
    RiskFactor: Individual risk factor with name and contribution (NEM-3603)
    ConfidenceFactors: Breakdown of confidence metrics (NEM-3606)
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


class RiskFactor(BaseModel):
    """A single risk factor contributing to the overall risk score (NEM-3603).

    Each risk factor represents a specific aspect of the detection that
    influenced the final risk score, along with its contribution weight.

    Attributes:
        name: Name of the risk factor (e.g., "unknown_person", "entry_zone")
        contribution: Contribution to risk score (positive increases risk, negative decreases)
        description: Human-readable explanation of this factor
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "unknown_person",
                "contribution": 25,
                "description": "Unrecognized person detected near entry point",
            }
        }
    )

    name: str = Field(..., description="Name of the risk factor")
    contribution: int = Field(
        ...,
        ge=-100,
        le=100,
        description="Contribution to risk score (-100 to +100)",
    )
    description: str = Field(..., description="Human-readable explanation of this factor")


class ConfidenceFactors(BaseModel):
    """Breakdown of confidence metrics for the risk assessment (NEM-3606).

    This provides transparency into how confident the system is in its
    risk assessment, broken down by various quality metrics.

    Attributes:
        overall: Overall confidence in the risk score (0.0-1.0)
        detection_quality: Confidence based on detection quality/clarity
        data_completeness: Confidence based on available enrichment data
        temporal_context: Confidence based on time-of-day/baseline data
        model_agreement: Confidence based on consistency across models
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "overall": 0.85,
                "detection_quality": 0.9,
                "data_completeness": 0.8,
                "temporal_context": 0.75,
                "model_agreement": 0.95,
            }
        }
    )

    overall: float = Field(..., ge=0.0, le=1.0, description="Overall confidence score (0.0-1.0)")
    detection_quality: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence based on detection quality/clarity",
    )
    data_completeness: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence based on available enrichment data",
    )
    temporal_context: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence based on time-of-day/baseline data",
    )
    model_agreement: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence based on consistency across models",
    )

    @field_validator(
        "overall",
        "detection_quality",
        "data_completeness",
        "temporal_context",
        "model_agreement",
        mode="before",
    )
    @classmethod
    def clamp_confidence(cls, v: Any) -> float:
        """Clamp confidence values to 0.0-1.0 range."""
        if v is None:
            return 1.0
        try:
            val = float(v)
            return max(0.0, min(1.0, val))
        except (ValueError, TypeError):
            return 1.0


def infer_risk_level_from_score(score: int) -> RiskLevel:
    """Infer risk level from score using default thresholds.

    Uses Python 3.10+ structural pattern matching with guard clauses
    for clear, readable threshold-based classification.

    Args:
        score: Risk score (0-100)

    Returns:
        Inferred RiskLevel based on score thresholds
    """
    match score:
        case _ if score <= DEFAULT_LOW_MAX:
            return RiskLevel.LOW
        case _ if score <= DEFAULT_MEDIUM_MAX:
            return RiskLevel.MEDIUM
        case _ if score <= DEFAULT_HIGH_MAX:
            return RiskLevel.HIGH
        case _:
            return RiskLevel.CRITICAL


class LLMRiskResponse(BaseModel):
    """Validated risk assessment response from Nemotron LLM.

    This schema enforces strict validation rules:
    - risk_score must be an integer between 0 and 100
    - risk_level must be a valid RiskLevel enum value
    - summary and reasoning are required strings
    - risk_factors and confidence are optional (NEM-3603, NEM-3606)

    This schema should be used after raw LLM JSON has been parsed
    and normalized (e.g., via LLMRawResponse.to_validated_response()).

    Attributes:
        risk_score: Risk assessment score (0-100)
        risk_level: Risk classification level
        summary: Human-readable event summary
        reasoning: Detailed reasoning for the risk assessment
        risk_factors: Breakdown of factors contributing to risk score (NEM-3603)
        confidence: Confidence metrics for the assessment (NEM-3606)
    """

    model_config = ConfigDict(
        extra="ignore",  # Ignore extra fields from LLM output
        json_schema_extra={
            "example": {
                "risk_score": 75,
                "risk_level": "high",
                "summary": "Suspicious activity detected at front entrance",
                "reasoning": "Person detected at unusual time with unknown vehicle",
                "risk_factors": [
                    {
                        "name": "unknown_person",
                        "contribution": 30,
                        "description": "Unrecognized person",
                    },
                    {
                        "name": "entry_zone",
                        "contribution": 20,
                        "description": "Near entry point",
                    },
                ],
                "confidence": {
                    "overall": 0.85,
                    "detection_quality": 0.9,
                    "data_completeness": 0.8,
                },
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
    risk_factors: list[RiskFactor] | None = Field(
        default=None,
        description="Breakdown of factors contributing to risk score (NEM-3603)",
    )
    confidence: ConfidenceFactors | None = Field(
        default=None,
        description="Confidence metrics for the assessment (NEM-3606)",
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
    - Missing/malformed risk_factors (NEM-3603)
    - Missing/malformed confidence (NEM-3606)

    Use the to_validated_response() method to convert to a strictly
    validated LLMRiskResponse.

    Attributes:
        risk_score: Raw risk score (may be out of range)
        risk_level: Raw risk level string (may be invalid)
        summary: Optional event summary
        reasoning: Optional reasoning text
        risk_factors: Optional list of risk factors (NEM-3603)
        confidence: Optional confidence metrics (NEM-3606)
    """

    model_config = ConfigDict(
        extra="ignore",  # Ignore extra fields from LLM
        json_schema_extra={
            "example": {
                "risk_score": 150,
                "risk_level": "EXTREME",
                "summary": "Test",
                "reasoning": "Test",
                "risk_factors": [
                    {"name": "test_factor", "contribution": 50, "description": "Test factor"},
                ],
                "confidence": {"overall": 0.85},
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
    risk_factors: list[dict[str, Any]] | None = Field(
        None,
        description="Raw risk factors from LLM (NEM-3603)",
    )
    confidence: dict[str, Any] | None = Field(
        None,
        description="Raw confidence metrics from LLM (NEM-3606)",
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
        5. Validates and normalizes risk_factors (NEM-3603)
        6. Validates and normalizes confidence (NEM-3606)

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

        # Parse and validate risk_factors (NEM-3603)
        validated_risk_factors: list[RiskFactor] | None = None
        if self.risk_factors:
            validated_risk_factors = []
            for factor in self.risk_factors:
                try:
                    if isinstance(factor, dict):
                        # Ensure required fields exist
                        name = factor.get("name", "unknown")
                        contribution = factor.get("contribution", 0)
                        description = factor.get("description", "")
                        # Clamp contribution to valid range
                        try:
                            contribution = max(-100, min(100, int(contribution)))
                        except (ValueError, TypeError):
                            contribution = 0
                        validated_risk_factors.append(
                            RiskFactor(
                                name=str(name),
                                contribution=contribution,
                                description=str(description) if description else str(name),
                            )
                        )
                except (ValueError, TypeError, KeyError):
                    # Skip malformed factors - errors logged at higher level
                    pass
            if not validated_risk_factors:
                validated_risk_factors = None

        # Parse and validate confidence (NEM-3606)
        validated_confidence: ConfidenceFactors | None = None
        if self.confidence and isinstance(self.confidence, dict):
            try:
                # Extract overall confidence, default to 1.0 if not provided
                overall = self.confidence.get("overall", 1.0)
                validated_confidence = ConfidenceFactors(
                    overall=overall,
                    detection_quality=self.confidence.get("detection_quality", 1.0),
                    data_completeness=self.confidence.get("data_completeness", 1.0),
                    temporal_context=self.confidence.get("temporal_context", 1.0),
                    model_agreement=self.confidence.get("model_agreement", 1.0),
                )
            except (ValueError, TypeError, KeyError):
                # If parsing fails, leave as None - errors logged at higher level
                validated_confidence = None

        return LLMRiskResponse(
            risk_score=score,
            risk_level=normalized_level,
            summary=summary,
            reasoning=reasoning,
            risk_factors=validated_risk_factors,
            confidence=validated_confidence,
        )
