"""Pydantic schemas for LLM response validation.

This module defines the expected structure of LLM (Nemotron) responses
for risk assessment. These schemas provide:
- Type safety and validation
- Automatic coercion of common LLM response variations
- Clear error messages for malformed responses
- Default values for missing optional fields

LLM Response Format:
The Nemotron LLM returns JSON with risk assessment data. The response
may include additional fields beyond the core ones (entities, flags, etc.)
depending on the prompt template used.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator


class RiskLevel(str, Enum):
    """Valid risk levels for security events.

    Risk levels follow the severity taxonomy:
    - LOW: 0-29 risk score
    - MEDIUM: 30-59 risk score
    - HIGH: 60-84 risk score
    - CRITICAL: 85-100 risk score
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatLevel(str, Enum):
    """Threat level for individual entities detected."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EntityType(str, Enum):
    """Types of entities that can be detected."""

    PERSON = "person"
    VEHICLE = "vehicle"
    PET = "pet"


class FlagSeverity(str, Enum):
    """Severity levels for security flags."""

    WARNING = "warning"
    ALERT = "alert"
    CRITICAL = "critical"


class FlagType(str, Enum):
    """Types of security flags that can be raised."""

    VIOLENCE = "violence"
    SUSPICIOUS_ATTIRE = "suspicious_attire"
    VEHICLE_DAMAGE = "vehicle_damage"
    UNUSUAL_BEHAVIOR = "unusual_behavior"
    QUALITY_ISSUE = "quality_issue"


class DetectionQuality(str, Enum):
    """Detection quality assessment."""

    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


class WeatherImpact(str, Enum):
    """Weather impact on detection accuracy."""

    NONE = "none"
    MINOR = "minor"
    SIGNIFICANT = "significant"


class EnrichmentCoverage(str, Enum):
    """Level of enrichment data coverage."""

    FULL = "full"
    PARTIAL = "partial"
    MINIMAL = "minimal"


class LLMEntity(BaseModel):
    """Individual entity detected in the security event.

    Entities represent persons, vehicles, or pets identified in the scene
    with their descriptions and assessed threat levels.
    """

    model_config = ConfigDict(extra="allow")

    type: EntityType = Field(..., description="Type of entity detected")
    description: str = Field(..., description="Detailed description of the entity")
    threat_level: ThreatLevel = Field(
        ThreatLevel.LOW, description="Assessed threat level for this entity"
    )

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, v: Any) -> EntityType:
        """Normalize entity type to lowercase enum value."""
        if isinstance(v, EntityType):
            return v
        if isinstance(v, str):
            return EntityType(v.lower())
        raise ValueError(f"Invalid entity type: {v}")

    @field_validator("threat_level", mode="before")
    @classmethod
    def normalize_threat_level(cls, v: Any) -> ThreatLevel:
        """Normalize threat level to lowercase enum value."""
        if isinstance(v, ThreatLevel):
            return v
        if isinstance(v, str):
            return ThreatLevel(v.lower())
        return ThreatLevel.LOW


class LLMFlag(BaseModel):
    """Security flag raised during analysis.

    Flags indicate specific security concerns detected during the
    analysis, such as violence, suspicious attire, or quality issues.
    """

    model_config = ConfigDict(extra="allow")

    type: FlagType = Field(..., description="Type of security flag")
    description: str = Field(..., description="Description of the flagged concern")
    severity: FlagSeverity = Field(FlagSeverity.WARNING, description="Severity of the flag")

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, v: Any) -> FlagType:
        """Normalize flag type to lowercase enum value."""
        if isinstance(v, FlagType):
            return v
        if isinstance(v, str):
            return FlagType(v.lower())
        raise ValueError(f"Invalid flag type: {v}")

    @field_validator("severity", mode="before")
    @classmethod
    def normalize_severity(cls, v: Any) -> FlagSeverity:
        """Normalize severity to lowercase enum value."""
        if isinstance(v, FlagSeverity):
            return v
        if isinstance(v, str):
            return FlagSeverity(v.lower())
        return FlagSeverity.WARNING


class LLMConfidenceFactors(BaseModel):
    """Confidence factors affecting the analysis reliability.

    These factors help interpret the reliability of the risk assessment
    based on detection quality, weather conditions, and enrichment coverage.
    """

    model_config = ConfigDict(extra="allow")

    detection_quality: DetectionQuality = Field(
        DetectionQuality.GOOD, description="Quality of the detections"
    )
    weather_impact: WeatherImpact = Field(
        WeatherImpact.NONE, description="Impact of weather on accuracy"
    )
    enrichment_coverage: EnrichmentCoverage = Field(
        EnrichmentCoverage.FULL, description="Coverage of enrichment data"
    )

    @field_validator("detection_quality", mode="before")
    @classmethod
    def normalize_detection_quality(cls, v: Any) -> DetectionQuality:
        """Normalize detection quality."""
        if isinstance(v, DetectionQuality):
            return v
        if isinstance(v, str):
            try:
                return DetectionQuality(v.lower())
            except ValueError:
                return DetectionQuality.GOOD
        return DetectionQuality.GOOD

    @field_validator("weather_impact", mode="before")
    @classmethod
    def normalize_weather_impact(cls, v: Any) -> WeatherImpact:
        """Normalize weather impact."""
        if isinstance(v, WeatherImpact):
            return v
        if isinstance(v, str):
            try:
                return WeatherImpact(v.lower())
            except ValueError:
                return WeatherImpact.NONE
        return WeatherImpact.NONE

    @field_validator("enrichment_coverage", mode="before")
    @classmethod
    def normalize_enrichment_coverage(cls, v: Any) -> EnrichmentCoverage:
        """Normalize enrichment coverage."""
        if isinstance(v, EnrichmentCoverage):
            return v
        if isinstance(v, str):
            try:
                return EnrichmentCoverage(v.lower())
            except ValueError:
                return EnrichmentCoverage.FULL
        return EnrichmentCoverage.FULL


class LLMRiskResponse(BaseModel):
    """Schema for validating LLM risk assessment responses.

    This is the primary schema for parsing and validating the JSON response
    from the Nemotron LLM. It handles:
    - Core required fields (risk_score, risk_level, summary, reasoning)
    - Optional enhanced fields (entities, flags, recommended_action)
    - Confidence factors for reliability assessment
    - Automatic type coercion and validation

    The schema is designed to be resilient to LLM output variations:
    - Risk scores are clamped to 0-100 range
    - Risk levels are case-insensitive
    - Missing optional fields get sensible defaults
    - Extra fields are allowed but not required
    """

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "examples": [
                {
                    "risk_score": 75,
                    "risk_level": "high",
                    "summary": "Multiple persons detected at unusual time near entry point",
                    "reasoning": "Two unidentified individuals approached the front entrance "
                    "at 2:30 AM. Both are wearing dark hoodies with hoods up, which is "
                    "suspicious given the time and location. Cross-camera analysis shows "
                    "they arrived in an unmarked van.",
                    "entities": [
                        {
                            "type": "person",
                            "description": "Individual in dark hoodie, face obscured",
                            "threat_level": "high",
                        },
                        {
                            "type": "vehicle",
                            "description": "White unmarked van, license plate partially visible",
                            "threat_level": "medium",
                        },
                    ],
                    "flags": [
                        {
                            "type": "suspicious_attire",
                            "description": "Face covering detected on both individuals",
                            "severity": "alert",
                        }
                    ],
                    "recommended_action": "Activate external lights, notify homeowner, "
                    "capture additional footage",
                    "confidence_factors": {
                        "detection_quality": "good",
                        "weather_impact": "none",
                        "enrichment_coverage": "full",
                    },
                }
            ]
        },
    )

    # Core required fields
    risk_score: Annotated[int, Field(ge=0, le=100, description="Risk score from 0-100")]
    risk_level: RiskLevel = Field(..., description="Risk level category")
    summary: str = Field(..., min_length=1, description="Brief 1-2 sentence summary")
    reasoning: str = Field(..., min_length=1, description="Detailed reasoning explanation")

    # Optional enhanced fields (from advanced prompt templates)
    entities: list[LLMEntity] = Field(
        default_factory=list, description="Detected entities with threat assessments"
    )
    flags: list[LLMFlag] = Field(
        default_factory=list, description="Security flags raised during analysis"
    )
    recommended_action: str | None = Field(None, description="Recommended action to take")
    confidence_factors: LLMConfidenceFactors | None = Field(
        None, description="Factors affecting analysis confidence"
    )

    @field_validator("risk_score", mode="before")
    @classmethod
    def coerce_risk_score(cls, v: Any) -> int:
        """Coerce risk_score to integer and clamp to 0-100.

        Handles various LLM output formats:
        - Integer: 75 -> 75
        - Float: 75.5 -> 75
        - String: "75" -> 75
        - Out of range: 150 -> 100, -10 -> 0
        - Invalid: "high" -> raises ValueError
        """
        if v is None:
            raise ValueError("risk_score is required")

        try:
            score = int(float(v))
        except (ValueError, TypeError) as e:
            raise ValueError(f"risk_score must be numeric, got: {v}") from e

        # Clamp to valid range
        return max(0, min(100, score))

    @field_validator("risk_level", mode="before")
    @classmethod
    def coerce_risk_level(cls, v: Any) -> RiskLevel:
        """Coerce risk_level to enum, handling case variations.

        Handles various LLM output formats:
        - Lowercase: "high" -> RiskLevel.HIGH
        - Uppercase: "HIGH" -> RiskLevel.HIGH
        - Mixed case: "High" -> RiskLevel.HIGH
        - Enum value: RiskLevel.HIGH -> RiskLevel.HIGH
        - Invalid: "danger" -> raises ValueError
        """
        if isinstance(v, RiskLevel):
            return v

        if isinstance(v, str):
            normalized = v.lower().strip()
            try:
                return RiskLevel(normalized)
            except ValueError:
                # Invalid risk level string - fall through to raise a more descriptive error
                # that lists valid options rather than showing the raw ValueError.
                # See: NEM-2540 for rationale
                pass

        raise ValueError(f"risk_level must be one of: low, medium, high, critical. Got: {v}")

    @field_validator("summary", mode="before")
    @classmethod
    def coerce_summary(cls, v: Any) -> str:
        """Coerce summary to string, with fallback for None/empty."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return "Risk analysis completed"
        return str(v).strip()

    @field_validator("reasoning", mode="before")
    @classmethod
    def coerce_reasoning(cls, v: Any) -> str:
        """Coerce reasoning to string, with fallback for None/empty."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return "No detailed reasoning provided"
        return str(v).strip()

    @model_validator(mode="after")
    def ensure_consistency(self) -> LLMRiskResponse:
        """Ensure risk_score and risk_level are consistent.

        If the LLM provides inconsistent values (e.g., score=90, level="low"),
        we trust the risk_score and adjust the level accordingly.

        Thresholds (from backend severity taxonomy):
        - LOW: 0-29
        - MEDIUM: 30-59
        - HIGH: 60-84
        - CRITICAL: 85-100
        """
        score = self.risk_score

        # Determine expected level from score
        if score >= 85:
            expected_level = RiskLevel.CRITICAL
        elif score >= 60:
            expected_level = RiskLevel.HIGH
        elif score >= 30:
            expected_level = RiskLevel.MEDIUM
        else:
            expected_level = RiskLevel.LOW

        # If levels don't match, trust the score
        if self.risk_level != expected_level:
            # Log this mismatch in the future, for now just correct it
            # This handles cases where LLM provides inconsistent values
            object.__setattr__(self, "risk_level", expected_level)

        return self

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for backwards compatibility.

        Returns a dict matching the format expected by NemotronAnalyzer._validate_risk_data().
        Entities and flags are excluded as they're not stored in the Event model.
        """
        return {
            "risk_score": self.risk_score,
            "risk_level": self.risk_level.value,
            "summary": self.summary,
            "reasoning": self.reasoning,
        }


class LLMResponseParseError(Exception):
    """Exception raised when LLM response cannot be parsed.

    Attributes:
        raw_response: The raw response text that failed to parse
        message: Human-readable error message
    """

    def __init__(self, message: str, raw_response: str | None = None):
        """Initialize parse error.

        Args:
            message: Human-readable error message
            raw_response: Optional raw response text that failed to parse
        """
        super().__init__(message)
        self.raw_response = raw_response
        self.message = message


# =============================================================================
# Module-level TypeAdapter instance (NEM-3395)
# =============================================================================
#
# This TypeAdapter is created once at module load time to eliminate the overhead
# of creating adapters on each validation call. This provides significant
# performance improvement for hot path LLM response validation.

_llm_risk_response_adapter: TypeAdapter[LLMRiskResponse] = TypeAdapter(LLMRiskResponse)


def validate_llm_response(data: dict[str, Any]) -> LLMRiskResponse:
    """Validate and parse LLM response data into typed schema.

    This function wraps Pydantic validation with additional error handling
    to provide clear, actionable error messages. Uses a module-level TypeAdapter
    for optimal performance in hot paths.

    Args:
        data: Dictionary parsed from LLM JSON response

    Returns:
        Validated LLMRiskResponse with all fields properly typed

    Raises:
        LLMResponseParseError: If validation fails with details about the error
    """
    from pydantic import ValidationError

    try:
        return _llm_risk_response_adapter.validate_python(data)
    except ValidationError as e:
        # Extract readable error messages
        errors = []
        for error in e.errors():
            field = ".".join(str(loc) for loc in error["loc"])
            msg = error["msg"]
            errors.append(f"{field}: {msg}")

        error_summary = "; ".join(errors)
        raise LLMResponseParseError(
            f"Invalid LLM response: {error_summary}",
            raw_response=str(data)[:500],  # Truncate for safety
        ) from e


def infer_risk_level_from_score(score: int) -> RiskLevel:
    """Infer risk level from a risk score.

    Uses the backend severity taxonomy:
    - LOW: 0-29
    - MEDIUM: 30-59
    - HIGH: 60-84
    - CRITICAL: 85-100

    Args:
        score: Risk score (0-100)

    Returns:
        Corresponding RiskLevel enum value
    """
    if score >= 85:
        return RiskLevel.CRITICAL
    elif score >= 60:
        return RiskLevel.HIGH
    elif score >= 30:
        return RiskLevel.MEDIUM
    else:
        return RiskLevel.LOW
