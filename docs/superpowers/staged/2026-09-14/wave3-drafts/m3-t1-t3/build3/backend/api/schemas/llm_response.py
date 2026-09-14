"""Pydantic schemas for LLM response validation.

This module defines schemas for validating and normalizing responses from the
Nemotron LLM service. The schemas provide type-safe parsing and validation
of risk assessment data returned by the LLM.

Schemas:
    LLMRiskResponse: Validated risk assessment with strict constraints
    LLMRawResponse: Lenient parsing for raw LLM JSON output
    RiskLevel: Enum of valid risk level values
    RiskFactor: Individual contributing factor to risk score (NEM-3603)
    RiskEntity: Entity identified in the risk analysis (NEM-3601)
    RiskFlag: Risk flags with severity levels (NEM-3601)
    ConfidenceFactors: Factors affecting confidence in the analysis (NEM-3601)

Constants:
    RISK_ANALYSIS_JSON_SCHEMA: JSON Schema for NVIDIA NIM guided_json (NEM-3725)
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

# =============================================================================
# JSON Schema for NVIDIA NIM guided_json Parameter (NEM-3725)
# =============================================================================

RISK_ANALYSIS_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "risk_score": {
            "type": "integer",
            "minimum": 0,
            "maximum": 100,
            "description": "Risk assessment score from 0 (no risk) to 100 (maximum risk)",
        },
        "risk_level": {
            "type": "string",
            "enum": ["low", "medium", "high", "critical"],
            "description": "Categorical risk classification based on score thresholds",
        },
        "summary": {
            "type": "string",
            "maxLength": 200,
            "description": "Concise human-readable summary of the detected activity",
        },
        "reasoning": {
            "type": "string",
            "description": "Detailed explanation of the risk assessment rationale",
        },
        "entities": {
            "type": "array",
            "description": "List of entities identified in the scene",
            "items": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["person", "vehicle", "animal", "object"],
                        "description": "Category of the detected entity",
                    },
                    "description": {
                        "type": "string",
                        "description": "Detailed description of the entity",
                    },
                    "threat_level": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "Threat level attributed to this entity",
                    },
                },
                "required": ["type", "description", "threat_level"],
            },
        },
        "recommended_action": {
            "type": "string",
            "enum": ["none", "review", "alert", "immediate_response"],
            "description": "Suggested action based on the risk assessment",
        },
    },
    "required": ["risk_score", "risk_level", "summary", "reasoning"],
}
"""JSON Schema for risk analysis responses compatible with NVIDIA NIM's guided_json.

This schema defines the expected output format for the Nemotron LLM when performing
risk analysis on security camera detections. It enforces:

- risk_score: Integer between 0-100
- risk_level: One of low, medium, high, critical
- summary: String with max 200 characters
- reasoning: String explaining the assessment
- entities: Optional array of detected entities with type constraints
- recommended_action: Optional enum of action types

Usage with NVIDIA NIM:
    ```python
    response = client.chat.completions.create(
        model="nemotron",
        messages=[...],
        extra_body={"guided_json": RISK_ANALYSIS_JSON_SCHEMA}
    )
    ```

See Also:
    - LLMRiskResponse: Pydantic model for validating parsed responses
    - LLMRawResponse: Lenient model for parsing raw LLM output
"""


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


# =============================================================================
# Advanced Risk Analysis Schemas (NEM-3601)
# =============================================================================


class RiskFactor(BaseModel):
    """Individual factor contributing to the overall risk score (NEM-3603).

    Risk factors represent specific aspects of the analysis that contribute
    positively or negatively to the overall risk score. Positive contributions
    increase risk (e.g., nighttime activity, unknown person), while negative
    contributions decrease risk (e.g., recognized face, routine timing).

    Attributes:
        factor_name: Name of the risk factor (e.g., "nighttime_activity", "recognized_face")
        contribution: Contribution to risk score (positive increases risk, negative decreases)
        description: Optional explanation of why this factor applies
    """

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "factor_name": "nighttime_activity",
                "contribution": 15.0,
                "description": "Activity detected outside normal hours (11 PM - 6 AM)",
            }
        },
    )

    factor_name: str = Field(
        ...,
        description="Name of the risk factor",
    )
    contribution: float = Field(
        ...,
        description="Contribution to risk score (positive increases, negative decreases)",
    )
    description: str | None = Field(
        None,
        description="Optional explanation of why this factor applies",
    )


class RiskEntity(BaseModel):
    """Entity identified during risk analysis.

    Entities represent objects of interest detected in the scene that
    contribute to the overall risk assessment (e.g., people, vehicles,
    packages).

    Attributes:
        type: Category of entity (e.g., "person", "vehicle", "package")
        description: Detailed description of the entity
        threat_level: Risk level attributed to this entity
    """

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "type": "person",
                "description": "Unknown individual near front entrance",
                "threat_level": "medium",
            }
        },
    )

    type: str = Field(
        ...,
        description="Category of entity (e.g., person, vehicle, package)",
    )
    description: str = Field(
        ...,
        description="Detailed description of the entity",
    )
    threat_level: Literal["low", "medium", "high"] = Field(
        ...,
        description="Risk level attributed to this entity",
    )


class RiskFlag(BaseModel):
    """Risk flag indicating a specific concern or anomaly.

    Flags represent specific behaviors, patterns, or conditions that
    warrant attention (e.g., loitering, nighttime activity, weapon detected).

    Attributes:
        type: Category of flag (e.g., "loitering", "weapon_detected")
        description: Explanation of the flag
        severity: How severe this flag is (warning, alert, critical)
    """

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "type": "loitering",
                "description": "Person has been stationary for over 5 minutes",
                "severity": "warning",
            }
        },
    )

    type: str = Field(
        ...,
        description="Category of flag (e.g., loitering, weapon_detected)",
    )
    description: str = Field(
        ...,
        description="Explanation of the flag",
    )
    severity: Literal["warning", "alert", "critical"] = Field(
        ...,
        description="Severity level of this flag",
    )


class ConfidenceFactors(BaseModel):
    """Factors affecting confidence in the risk analysis.

    These factors help explain the reliability of the risk assessment
    and can be used to understand when additional review may be needed.

    Attributes:
        detection_quality: Quality of the detection data (good, fair, poor)
        weather_impact: Impact of weather on detection accuracy
        enrichment_coverage: Completeness of enrichment data used
    """

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "detection_quality": "good",
                "weather_impact": "none",
                "enrichment_coverage": "full",
            }
        },
    )

    detection_quality: Literal["good", "fair", "poor"] = Field(
        default="good",
        description="Quality of the detection data",
    )
    weather_impact: Literal["none", "minor", "significant"] = Field(
        default="none",
        description="Impact of weather conditions on detection accuracy",
    )
    enrichment_coverage: Literal["full", "partial", "minimal"] = Field(
        default="full",
        description="Completeness of enrichment data available",
    )


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
        risk_factors: Individual factors contributing to the risk score (NEM-3603)
        entities: List of entities identified in the analysis (NEM-3601)
        flags: List of risk flags raised during analysis (NEM-3601)
        recommended_action: Suggested action to take (NEM-3601)
        confidence_factors: Factors affecting analysis confidence (NEM-3601)
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
                        "factor_name": "nighttime_activity",
                        "contribution": 15.0,
                        "description": "Activity detected outside normal hours",
                    },
                    {
                        "factor_name": "unknown_person",
                        "contribution": 20.0,
                        "description": "Person not recognized by face detection",
                    },
                    {
                        "factor_name": "routine_location",
                        "contribution": -10.0,
                        "description": "Activity at commonly used entrance",
                    },
                ],
                "entities": [
                    {
                        "type": "person",
                        "description": "Unknown individual",
                        "threat_level": "medium",
                    }
                ],
                "flags": [
                    {
                        "type": "nighttime_activity",
                        "description": "Activity detected outside normal hours",
                        "severity": "warning",
                    }
                ],
                "recommended_action": "Review camera footage",
                "confidence_factors": {
                    "detection_quality": "good",
                    "weather_impact": "none",
                    "enrichment_coverage": "full",
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
    # Risk factors breakdown (NEM-3603)
    risk_factors: list[RiskFactor] = Field(
        default_factory=list,
        description="Individual factors contributing to the risk score",
    )
    # Advanced fields (NEM-3601)
    entities: list[RiskEntity] = Field(
        default_factory=list,
        description="Entities identified in the analysis",
    )
    flags: list[RiskFlag] = Field(
        default_factory=list,
        description="Risk flags raised during analysis",
    )
    recommended_action: str | None = Field(
        default=None,
        description="Suggested action to take based on the analysis",
    )
    confidence_factors: ConfidenceFactors | None = Field(
        default=None,
        description="Factors affecting confidence in the analysis",
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
        risk_factors: Optional list of risk factors (NEM-3603)
        entities: Optional list of entities (NEM-3601)
        flags: Optional list of risk flags (NEM-3601)
        recommended_action: Optional recommended action (NEM-3601)
        confidence_factors: Optional confidence factors (NEM-3601)
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
    # Risk factors (NEM-3603) - stored as raw dicts for lenient parsing
    risk_factors: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Raw risk factors from LLM (validated during conversion)",
    )
    # Advanced fields (NEM-3601) - stored as raw dicts for lenient parsing
    entities: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Raw entities from LLM (validated during conversion)",
    )
    flags: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Raw flags from LLM (validated during conversion)",
    )
    recommended_action: str | None = Field(
        None,
        description="Recommended action (optional in raw response)",
    )
    confidence_factors: dict[str, Any] | None = Field(
        None,
        description="Raw confidence factors (validated during conversion)",
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
        5. Validates and converts risk factors (NEM-3603)
        6. Validates and converts advanced fields (NEM-3601)

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

        # Parse risk factors (NEM-3603)
        validated_risk_factors = self._parse_risk_factors()

        # Parse advanced fields (NEM-3601)
        validated_entities = self._parse_entities()
        validated_flags = self._parse_flags()
        validated_confidence_factors = self._parse_confidence_factors()

        return LLMRiskResponse(
            risk_score=score,
            risk_level=normalized_level,
            summary=summary,
            reasoning=reasoning,
            risk_factors=validated_risk_factors,
            entities=validated_entities,
            flags=validated_flags,
            recommended_action=self.recommended_action,
            confidence_factors=validated_confidence_factors,
        )

    def _parse_risk_factors(self) -> list[RiskFactor]:
        """Parse and validate risk factors from raw data (NEM-3603).

        Invalid risk factors are filtered out with debug logging to handle
        malformed LLM output gracefully.

        Returns:
            List of validated RiskFactor instances
        """
        validated: list[RiskFactor] = []
        for factor_data in self.risk_factors:
            try:
                validated.append(RiskFactor.model_validate(factor_data))
            except Exception as e:
                # Skip invalid risk factors with debug logging
                logger.debug("Skipping invalid risk factor: %s (error: %s)", factor_data, e)
        return validated

    def _parse_entities(self) -> list[RiskEntity]:
        """Parse and validate entities from raw data.

        Invalid entities are filtered out with debug logging to handle
        malformed LLM output gracefully.

        Returns:
            List of validated RiskEntity instances
        """
        validated: list[RiskEntity] = []
        for entity_data in self.entities:
            try:
                validated.append(RiskEntity.model_validate(entity_data))
            except Exception as e:
                # Skip invalid entities with debug logging
                logger.debug("Skipping invalid entity: %s (error: %s)", entity_data, e)
        return validated

    def _parse_flags(self) -> list[RiskFlag]:
        """Parse and validate flags from raw data.

        Invalid flags are filtered out with debug logging to handle
        malformed LLM output gracefully.

        Returns:
            List of validated RiskFlag instances
        """
        validated: list[RiskFlag] = []
        for flag_data in self.flags:
            try:
                validated.append(RiskFlag.model_validate(flag_data))
            except Exception as e:
                # Skip invalid flags with debug logging
                logger.debug("Skipping invalid flag: %s (error: %s)", flag_data, e)
        return validated

    def _parse_confidence_factors(self) -> ConfidenceFactors | None:
        """Parse and validate confidence factors from raw data.

        Returns None if confidence_factors is not provided or invalid.

        Returns:
            Validated ConfidenceFactors instance or None
        """
        if self.confidence_factors is None:
            return None
        try:
            return ConfidenceFactors.model_validate(self.confidence_factors)
        except Exception:
            return None


# =============================================================================
# Chain-of-Thought Reasoning Support (NEM-3727)
# =============================================================================


class LLMResponseWithReasoning(BaseModel):
    """LLM response with extracted chain-of-thought reasoning.

    This schema extends the standard risk response to include the model's
    reasoning process when chain-of-thought is enabled. The reasoning is
    extracted from <think>...</think> blocks in the LLM output.

    Use Cases:
        - Debugging risk assessments by reviewing the model's thought process
        - Auditing decisions for compliance and quality assurance
        - Improving prompts by understanding how the model reasons
        - Providing transparency in high-stakes risk evaluations

    Attributes:
        risk_score: Risk assessment score (0-100)
        risk_level: Risk classification level (low, medium, high, critical)
        summary: Human-readable event summary
        reasoning: Detailed reasoning for the risk assessment (from JSON)
        chain_of_thought: Raw reasoning from <think> blocks before JSON response.
            This captures the model's step-by-step thinking process. None if
            chain-of-thought reasoning was not enabled or no think block present.
        risk_factors: Individual factors contributing to the risk score
        entities: Entities identified in the analysis
        flags: Risk flags raised during analysis
        recommended_action: Suggested action to take
        confidence_factors: Factors affecting analysis confidence
    """

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "risk_score": 35,
                "risk_level": "medium",
                "summary": "Unknown person approaching front entrance at night",
                "reasoning": "Person detected at 11:42 PM approaching front door. "
                "No face match found. Time of day increases risk slightly.",
                "chain_of_thought": "Let me analyze this detection systematically:\n"
                "1. Time: 11:42 PM - outside normal hours (typically 7 AM - 10 PM)\n"
                "2. Location: Front entrance - a sensitive area\n"
                "3. Person: No face match in household database\n"
                "4. Behavior: Walking toward door, not lingering\n"
                "5. Context: No vehicle detected, could be neighbor or delivery\n\n"
                "Risk factors:\n"
                "- Late hour: +15 points\n"
                "- Unknown person: +20 points\n"
                "- Normal walking behavior: -10 points\n"
                "- No threatening items: -5 points\n\n"
                "Final assessment: Medium risk, worth noting but not alarming.",
                "risk_factors": [
                    {
                        "factor_name": "late_hour",
                        "contribution": 15.0,
                        "description": "Activity outside normal hours (11 PM)",
                    },
                    {
                        "factor_name": "unknown_person",
                        "contribution": 20.0,
                        "description": "No face match in household database",
                    },
                    {
                        "factor_name": "normal_behavior",
                        "contribution": -10.0,
                        "description": "Walking at normal pace, not lingering",
                    },
                ],
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
        description="Detailed reasoning for the risk assessment (from JSON response)",
    )
    chain_of_thought: str | None = Field(
        None,
        description="Raw chain-of-thought reasoning from <think> blocks. "
        "Captures the model's step-by-step thinking process before generating "
        "the final JSON response. None if CoT was not enabled.",
    )
    # Risk factors breakdown (NEM-3603)
    risk_factors: list[RiskFactor] = Field(
        default_factory=list,
        description="Individual factors contributing to the risk score",
    )
    # Advanced fields (NEM-3601)
    entities: list[RiskEntity] = Field(
        default_factory=list,
        description="Entities identified in the analysis",
    )
    flags: list[RiskFlag] = Field(
        default_factory=list,
        description="Risk flags raised during analysis",
    )
    recommended_action: str | None = Field(
        default=None,
        description="Suggested action to take based on the analysis",
    )
    confidence_factors: ConfidenceFactors | None = Field(
        default=None,
        description="Factors affecting confidence in the analysis",
    )

    @field_validator("risk_score", mode="before")
    @classmethod
    def coerce_risk_score(cls, v: Any) -> int:
        """Coerce risk_score to integer.

        Handles string numbers and floats from LLM output.
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
        """Validate and normalize risk_level to lowercase."""
        if isinstance(v, RiskLevel):
            return v.value
        if isinstance(v, str):
            normalized = v.lower()
            valid_values = [level.value for level in RiskLevel]
            if normalized in valid_values:
                return normalized
            raise ValueError(f"Invalid risk_level '{v}'. Must be one of: {valid_values}")
        raise ValueError(f"risk_level must be a string, got {type(v).__name__}")

    @classmethod
    def from_risk_response(
        cls,
        risk_response: LLMRiskResponse,
        chain_of_thought: str | None = None,
    ) -> LLMResponseWithReasoning:
        """Create LLMResponseWithReasoning from an existing LLMRiskResponse.

        This factory method allows adding chain-of-thought reasoning to an
        already-validated risk response.

        Args:
            risk_response: Validated LLMRiskResponse instance
            chain_of_thought: Optional reasoning extracted from <think> blocks

        Returns:
            LLMResponseWithReasoning with all fields from risk_response plus CoT
        """
        return cls(
            risk_score=risk_response.risk_score,
            risk_level=risk_response.risk_level,
            summary=risk_response.summary,
            reasoning=risk_response.reasoning,
            chain_of_thought=chain_of_thought if chain_of_thought else None,
            risk_factors=risk_response.risk_factors,
            entities=risk_response.entities,
            flags=risk_response.flags,
            recommended_action=risk_response.recommended_action,
            confidence_factors=risk_response.confidence_factors,
        )
