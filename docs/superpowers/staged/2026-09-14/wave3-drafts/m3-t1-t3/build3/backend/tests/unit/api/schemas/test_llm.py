"""Unit tests for LLM Pydantic schemas (backend/api/schemas/llm.py).

This module tests all Pydantic models used for LLM (Nemotron) response validation:
- All enum types (RiskLevel, ThreatLevel, EntityType, etc.)
- LLMEntity: Individual entity detection with threat assessment
- LLMFlag: Security flag with severity
- LLMConfidenceFactors: Confidence metrics for analysis
- LLMRiskResponse: Main risk assessment response with validators
- Helper functions: validate_llm_response, infer_risk_level_from_score
- Custom exception: LLMResponseParseError

Following TDD principles: comprehensive coverage of valid data, validation errors,
edge cases, defaults, and custom validators.
"""

import pytest
from pydantic import ValidationError

from backend.api.schemas.llm import (
    DetectionQuality,
    EnrichmentCoverage,
    EntityType,
    FlagSeverity,
    FlagType,
    LLMConfidenceFactors,
    LLMEntity,
    LLMFlag,
    LLMResponseParseError,
    LLMRiskResponse,
    RiskLevel,
    ThreatLevel,
    WeatherImpact,
    infer_risk_level_from_score,
    validate_llm_response,
)

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


class TestRiskLevelEnum:
    """Tests for RiskLevel enum."""

    def test_risk_level_values(self):
        """Test all RiskLevel enum values are accessible."""
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"

    def test_risk_level_string_inheritance(self):
        """Test RiskLevel inherits from str."""
        assert isinstance(RiskLevel.LOW, str)
        assert RiskLevel.HIGH == "high"

    def test_risk_level_iteration(self):
        """Test iterating over all RiskLevel values."""
        levels = [level.value for level in RiskLevel]
        assert levels == ["low", "medium", "high", "critical"]

    def test_risk_level_from_string(self):
        """Test creating RiskLevel from string."""
        assert RiskLevel("low") == RiskLevel.LOW
        assert RiskLevel("critical") == RiskLevel.CRITICAL

    def test_risk_level_invalid_string(self):
        """Test invalid string raises ValueError."""
        with pytest.raises(ValueError):
            RiskLevel("invalid")


class TestThreatLevelEnum:
    """Tests for ThreatLevel enum."""

    def test_threat_level_values(self):
        """Test all ThreatLevel enum values."""
        assert ThreatLevel.LOW.value == "low"
        assert ThreatLevel.MEDIUM.value == "medium"
        assert ThreatLevel.HIGH.value == "high"

    def test_threat_level_no_critical(self):
        """Test ThreatLevel does not have 'critical' (only 3 levels)."""
        levels = [level.value for level in ThreatLevel]
        assert "critical" not in levels
        assert len(levels) == 3


class TestEntityTypeEnum:
    """Tests for EntityType enum."""

    def test_entity_type_values(self):
        """Test all EntityType enum values."""
        assert EntityType.PERSON.value == "person"
        assert EntityType.VEHICLE.value == "vehicle"
        assert EntityType.PET.value == "pet"

    def test_entity_type_from_string(self):
        """Test creating EntityType from string."""
        assert EntityType("person") == EntityType.PERSON
        assert EntityType("vehicle") == EntityType.VEHICLE


class TestFlagSeverityEnum:
    """Tests for FlagSeverity enum."""

    def test_flag_severity_values(self):
        """Test all FlagSeverity enum values."""
        assert FlagSeverity.WARNING.value == "warning"
        assert FlagSeverity.ALERT.value == "alert"
        assert FlagSeverity.CRITICAL.value == "critical"


class TestFlagTypeEnum:
    """Tests for FlagType enum."""

    def test_flag_type_values(self):
        """Test all FlagType enum values."""
        assert FlagType.VIOLENCE.value == "violence"
        assert FlagType.SUSPICIOUS_ATTIRE.value == "suspicious_attire"
        assert FlagType.VEHICLE_DAMAGE.value == "vehicle_damage"
        assert FlagType.UNUSUAL_BEHAVIOR.value == "unusual_behavior"
        assert FlagType.QUALITY_ISSUE.value == "quality_issue"

    def test_flag_type_count(self):
        """Test FlagType has exactly 5 types."""
        assert len(list(FlagType)) == 5


class TestDetectionQualityEnum:
    """Tests for DetectionQuality enum."""

    def test_detection_quality_values(self):
        """Test all DetectionQuality enum values."""
        assert DetectionQuality.GOOD.value == "good"
        assert DetectionQuality.FAIR.value == "fair"
        assert DetectionQuality.POOR.value == "poor"


class TestWeatherImpactEnum:
    """Tests for WeatherImpact enum."""

    def test_weather_impact_values(self):
        """Test all WeatherImpact enum values."""
        assert WeatherImpact.NONE.value == "none"
        assert WeatherImpact.MINOR.value == "minor"
        assert WeatherImpact.SIGNIFICANT.value == "significant"


class TestEnrichmentCoverageEnum:
    """Tests for EnrichmentCoverage enum."""

    def test_enrichment_coverage_values(self):
        """Test all EnrichmentCoverage enum values."""
        assert EnrichmentCoverage.FULL.value == "full"
        assert EnrichmentCoverage.PARTIAL.value == "partial"
        assert EnrichmentCoverage.MINIMAL.value == "minimal"


class TestLLMEntity:
    """Tests for LLMEntity schema."""

    def test_valid_entity_all_fields(self):
        """Test creating valid entity with all fields."""
        entity = LLMEntity(
            type=EntityType.PERSON,
            description="Person in dark hoodie",
            threat_level=ThreatLevel.HIGH,
        )
        assert entity.type == EntityType.PERSON
        assert entity.description == "Person in dark hoodie"
        assert entity.threat_level == ThreatLevel.HIGH

    def test_entity_default_threat_level(self):
        """Test entity uses LOW as default threat level."""
        entity = LLMEntity(
            type=EntityType.VEHICLE,
            description="Blue sedan",
        )
        assert entity.threat_level == ThreatLevel.LOW

    def test_entity_type_normalization_uppercase(self):
        """Test entity type normalizes uppercase to lowercase."""
        entity = LLMEntity(
            type="PERSON",  # type: ignore[arg-type]
            description="Test person",
        )
        assert entity.type == EntityType.PERSON

    def test_entity_type_normalization_mixed_case(self):
        """Test entity type normalizes mixed case to lowercase."""
        entity = LLMEntity(
            type="Vehicle",  # type: ignore[arg-type]
            description="Test vehicle",
        )
        assert entity.type == EntityType.VEHICLE

    def test_entity_threat_level_normalization(self):
        """Test threat level normalizes to lowercase enum."""
        entity = LLMEntity(
            type=EntityType.PERSON,
            description="Test",
            threat_level="HIGH",  # type: ignore[arg-type]
        )
        assert entity.threat_level == ThreatLevel.HIGH

    def test_entity_threat_level_invalid_raises_error(self):
        """Test invalid threat level raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            LLMEntity(
                type=EntityType.PERSON,
                description="Test",
                threat_level="invalid",  # type: ignore[arg-type]
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("threat_level",) for e in errors)

    def test_entity_threat_level_non_string_defaults_to_low(self):
        """Test non-string threat level (like int) defaults to LOW."""
        entity = LLMEntity(
            type=EntityType.PERSON,
            description="Test",
            threat_level=123,  # type: ignore[arg-type]
        )
        assert entity.threat_level == ThreatLevel.LOW

    def test_entity_type_invalid_raises_error(self):
        """Test invalid entity type raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            LLMEntity(
                type="invalid_type",  # type: ignore[arg-type]
                description="Test",
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("type",) for e in errors)

    def test_entity_missing_type_fails(self):
        """Test missing type raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            LLMEntity(description="Test")  # type: ignore[call-arg]
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("type",) for e in errors)

    def test_entity_missing_description_fails(self):
        """Test missing description raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            LLMEntity(type=EntityType.PERSON)  # type: ignore[call-arg]
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("description",) for e in errors)

    def test_entity_empty_description_allowed(self):
        """Test empty string description is allowed (min_length not enforced)."""
        entity = LLMEntity(
            type=EntityType.PET,
            description="",
        )
        assert entity.description == ""

    def test_entity_allows_extra_fields(self):
        """Test entity allows extra fields (ConfigDict extra='allow')."""
        entity = LLMEntity(
            type=EntityType.PERSON,
            description="Test",
            custom_field="custom_value",  # type: ignore[call-arg]
        )
        assert entity.type == EntityType.PERSON

    def test_entity_serialization(self):
        """Test entity serializes to dict correctly."""
        entity = LLMEntity(
            type=EntityType.VEHICLE,
            description="Red truck",
            threat_level=ThreatLevel.MEDIUM,
        )
        data = entity.model_dump()
        assert data["type"] == "vehicle"
        assert data["description"] == "Red truck"
        assert data["threat_level"] == "medium"

    def test_entity_from_dict(self):
        """Test creating entity from dictionary."""
        data = {
            "type": "pet",
            "description": "Large dog",
            "threat_level": "low",
        }
        entity = LLMEntity.model_validate(data)
        assert entity.type == EntityType.PET
        assert entity.threat_level == ThreatLevel.LOW


class TestLLMFlag:
    """Tests for LLMFlag schema."""

    def test_valid_flag_all_fields(self):
        """Test creating valid flag with all fields."""
        flag = LLMFlag(
            type=FlagType.SUSPICIOUS_ATTIRE,
            description="Face covering detected",
            severity=FlagSeverity.ALERT,
        )
        assert flag.type == FlagType.SUSPICIOUS_ATTIRE
        assert flag.description == "Face covering detected"
        assert flag.severity == FlagSeverity.ALERT

    def test_flag_default_severity(self):
        """Test flag uses WARNING as default severity."""
        flag = LLMFlag(
            type=FlagType.QUALITY_ISSUE,
            description="Low image quality",
        )
        assert flag.severity == FlagSeverity.WARNING

    def test_flag_type_normalization(self):
        """Test flag type normalizes to lowercase enum."""
        flag = LLMFlag(
            type="VIOLENCE",  # type: ignore[arg-type]
            description="Test",
        )
        assert flag.type == FlagType.VIOLENCE

    def test_flag_severity_normalization(self):
        """Test flag severity normalizes to lowercase enum."""
        flag = LLMFlag(
            type=FlagType.UNUSUAL_BEHAVIOR,
            description="Test",
            severity="CRITICAL",  # type: ignore[arg-type]
        )
        assert flag.severity == FlagSeverity.CRITICAL

    def test_flag_severity_invalid_raises_error(self):
        """Test invalid severity string raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            LLMFlag(
                type=FlagType.QUALITY_ISSUE,
                description="Test",
                severity="invalid",  # type: ignore[arg-type]
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("severity",) for e in errors)

    def test_flag_severity_non_string_defaults_to_warning(self):
        """Test non-string severity (like int) defaults to WARNING."""
        flag = LLMFlag(
            type=FlagType.QUALITY_ISSUE,
            description="Test",
            severity=999,  # type: ignore[arg-type]
        )
        assert flag.severity == FlagSeverity.WARNING

    def test_flag_type_invalid_raises_error(self):
        """Test invalid flag type raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            LLMFlag(
                type="invalid_flag",  # type: ignore[arg-type]
                description="Test",
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("type",) for e in errors)

    def test_flag_missing_type_fails(self):
        """Test missing type raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            LLMFlag(description="Test")  # type: ignore[call-arg]
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("type",) for e in errors)

    def test_flag_missing_description_fails(self):
        """Test missing description raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            LLMFlag(type=FlagType.VIOLENCE)  # type: ignore[call-arg]
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("description",) for e in errors)

    def test_flag_allows_extra_fields(self):
        """Test flag allows extra fields."""
        flag = LLMFlag(
            type=FlagType.VEHICLE_DAMAGE,
            description="Test",
            extra_data="extra",  # type: ignore[call-arg]
        )
        assert flag.type == FlagType.VEHICLE_DAMAGE

    def test_flag_serialization(self):
        """Test flag serializes correctly."""
        flag = LLMFlag(
            type=FlagType.SUSPICIOUS_ATTIRE,
            description="Masked individual",
            severity=FlagSeverity.ALERT,
        )
        data = flag.model_dump()
        assert data["type"] == "suspicious_attire"
        assert data["description"] == "Masked individual"
        assert data["severity"] == "alert"


class TestLLMConfidenceFactors:
    """Tests for LLMConfidenceFactors schema."""

    def test_confidence_factors_all_defaults(self):
        """Test confidence factors with all default values."""
        factors = LLMConfidenceFactors()
        assert factors.detection_quality == DetectionQuality.GOOD
        assert factors.weather_impact == WeatherImpact.NONE
        assert factors.enrichment_coverage == EnrichmentCoverage.FULL

    def test_confidence_factors_all_fields(self):
        """Test confidence factors with all fields set."""
        factors = LLMConfidenceFactors(
            detection_quality=DetectionQuality.POOR,
            weather_impact=WeatherImpact.SIGNIFICANT,
            enrichment_coverage=EnrichmentCoverage.MINIMAL,
        )
        assert factors.detection_quality == DetectionQuality.POOR
        assert factors.weather_impact == WeatherImpact.SIGNIFICANT
        assert factors.enrichment_coverage == EnrichmentCoverage.MINIMAL

    def test_confidence_factors_detection_quality_normalization(self):
        """Test detection quality normalizes to lowercase."""
        factors = LLMConfidenceFactors(detection_quality="FAIR")  # type: ignore[arg-type]
        assert factors.detection_quality == DetectionQuality.FAIR

    def test_confidence_factors_weather_impact_normalization(self):
        """Test weather impact normalizes to lowercase."""
        factors = LLMConfidenceFactors(weather_impact="MINOR")  # type: ignore[arg-type]
        assert factors.weather_impact == WeatherImpact.MINOR

    def test_confidence_factors_enrichment_coverage_normalization(self):
        """Test enrichment coverage normalizes to lowercase."""
        factors = LLMConfidenceFactors(enrichment_coverage="PARTIAL")  # type: ignore[arg-type]
        assert factors.enrichment_coverage == EnrichmentCoverage.PARTIAL

    def test_confidence_factors_invalid_detection_quality_defaults(self):
        """Test invalid detection quality defaults to GOOD."""
        factors = LLMConfidenceFactors(detection_quality="invalid")  # type: ignore[arg-type]
        assert factors.detection_quality == DetectionQuality.GOOD

    def test_confidence_factors_invalid_weather_impact_defaults(self):
        """Test invalid weather impact defaults to NONE."""
        factors = LLMConfidenceFactors(weather_impact="invalid")  # type: ignore[arg-type]
        assert factors.weather_impact == WeatherImpact.NONE

    def test_confidence_factors_invalid_enrichment_coverage_defaults(self):
        """Test invalid enrichment coverage defaults to FULL."""
        factors = LLMConfidenceFactors(enrichment_coverage="invalid")  # type: ignore[arg-type]
        assert factors.enrichment_coverage == EnrichmentCoverage.FULL

    def test_confidence_factors_allows_extra_fields(self):
        """Test confidence factors allows extra fields."""
        factors = LLMConfidenceFactors(
            detection_quality=DetectionQuality.GOOD,
            custom_field="custom",  # type: ignore[call-arg]
        )
        assert factors.detection_quality == DetectionQuality.GOOD

    def test_confidence_factors_serialization(self):
        """Test confidence factors serializes correctly."""
        factors = LLMConfidenceFactors(
            detection_quality=DetectionQuality.FAIR,
            weather_impact=WeatherImpact.MINOR,
            enrichment_coverage=EnrichmentCoverage.PARTIAL,
        )
        data = factors.model_dump()
        assert data["detection_quality"] == "fair"
        assert data["weather_impact"] == "minor"
        assert data["enrichment_coverage"] == "partial"


class TestLLMRiskResponse:
    """Tests for LLMRiskResponse schema."""

    def test_valid_response_required_fields_only(self):
        """Test valid response with only required fields."""
        response = LLMRiskResponse(
            risk_score=50,
            risk_level=RiskLevel.MEDIUM,
            summary="Normal activity detected",
            reasoning="Routine daytime visitor",
        )
        assert response.risk_score == 50
        assert response.risk_level == RiskLevel.MEDIUM
        assert response.summary == "Normal activity detected"
        assert response.reasoning == "Routine daytime visitor"
        assert response.entities == []
        assert response.flags == []
        assert response.recommended_action is None
        assert response.confidence_factors is None

    def test_valid_response_all_fields(self):
        """Test valid response with all optional fields."""
        entities = [
            LLMEntity(
                type=EntityType.PERSON,
                description="Person in hoodie",
                threat_level=ThreatLevel.HIGH,
            )
        ]
        flags = [
            LLMFlag(
                type=FlagType.SUSPICIOUS_ATTIRE,
                description="Face covered",
                severity=FlagSeverity.ALERT,
            )
        ]
        confidence = LLMConfidenceFactors(
            detection_quality=DetectionQuality.GOOD,
            weather_impact=WeatherImpact.NONE,
            enrichment_coverage=EnrichmentCoverage.FULL,
        )

        response = LLMRiskResponse(
            risk_score=75,
            risk_level=RiskLevel.HIGH,
            summary="Suspicious activity",
            reasoning="Multiple red flags detected",
            entities=entities,
            flags=flags,
            recommended_action="Notify homeowner",
            confidence_factors=confidence,
        )

        assert response.risk_score == 75
        assert len(response.entities) == 1
        assert len(response.flags) == 1
        assert response.recommended_action == "Notify homeowner"
        assert response.confidence_factors is not None

    def test_risk_score_coercion_from_float(self):
        """Test risk_score coerces float to int."""
        response = LLMRiskResponse(
            risk_score=75.8,  # type: ignore[arg-type]
            risk_level=RiskLevel.HIGH,
            summary="Test",
            reasoning="Test",
        )
        assert response.risk_score == 75
        assert isinstance(response.risk_score, int)

    def test_risk_score_coercion_from_string(self):
        """Test risk_score coerces string number to int."""
        response = LLMRiskResponse(
            risk_score="65",  # type: ignore[arg-type]
            risk_level=RiskLevel.HIGH,
            summary="Test",
            reasoning="Test",
        )
        assert response.risk_score == 65
        assert isinstance(response.risk_score, int)

    def test_risk_score_clamping_upper_bound(self):
        """Test risk_score clamps values above 100."""
        response = LLMRiskResponse(
            risk_score=150,  # type: ignore[arg-type]
            risk_level=RiskLevel.CRITICAL,
            summary="Test",
            reasoning="Test",
        )
        assert response.risk_score == 100

    def test_risk_score_clamping_lower_bound(self):
        """Test risk_score clamps negative values to 0."""
        response = LLMRiskResponse(
            risk_score=-50,  # type: ignore[arg-type]
            risk_level=RiskLevel.LOW,
            summary="Test",
            reasoning="Test",
        )
        assert response.risk_score == 0

    def test_risk_score_none_raises_error(self):
        """Test None risk_score raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            LLMRiskResponse(
                risk_score=None,  # type: ignore[arg-type]
                risk_level=RiskLevel.MEDIUM,
                summary="Test",
                reasoning="Test",
            )
        errors = exc_info.value.errors()
        assert any("risk_score" in str(e) for e in errors)

    def test_risk_score_invalid_string_raises_error(self):
        """Test non-numeric string raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            LLMRiskResponse(
                risk_score="not_a_number",  # type: ignore[arg-type]
                risk_level=RiskLevel.MEDIUM,
                summary="Test",
                reasoning="Test",
            )
        errors = exc_info.value.errors()
        assert any("risk_score" in str(e) for e in errors)

    def test_risk_level_coercion_lowercase(self):
        """Test risk_level coerces lowercase string to enum."""
        response = LLMRiskResponse(
            risk_score=75,
            risk_level="high",  # type: ignore[arg-type]
            summary="Test",
            reasoning="Test",
        )
        assert response.risk_level == RiskLevel.HIGH

    def test_risk_level_coercion_uppercase(self):
        """Test risk_level coerces uppercase string to enum."""
        response = LLMRiskResponse(
            risk_score=30,
            risk_level="MEDIUM",  # type: ignore[arg-type]
            summary="Test",
            reasoning="Test",
        )
        assert response.risk_level == RiskLevel.MEDIUM

    def test_risk_level_coercion_mixed_case(self):
        """Test risk_level coerces mixed case to enum."""
        response = LLMRiskResponse(
            risk_score=90,
            risk_level="Critical",  # type: ignore[arg-type]
            summary="Test",
            reasoning="Test",
        )
        assert response.risk_level == RiskLevel.CRITICAL

    def test_risk_level_invalid_raises_error(self):
        """Test invalid risk_level raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            LLMRiskResponse(
                risk_score=50,
                risk_level="invalid_level",  # type: ignore[arg-type]
                summary="Test",
                reasoning="Test",
            )
        errors = exc_info.value.errors()
        assert any("risk_level" in str(e) for e in errors)

    def test_summary_coercion_none_to_default(self):
        """Test None summary gets default value."""
        response = LLMRiskResponse(
            risk_score=50,
            risk_level=RiskLevel.MEDIUM,
            summary=None,  # type: ignore[arg-type]
            reasoning="Test",
        )
        assert response.summary == "Risk analysis completed"

    def test_summary_coercion_empty_string_to_default(self):
        """Test empty string summary gets default value."""
        response = LLMRiskResponse(
            risk_score=50,
            risk_level=RiskLevel.MEDIUM,
            summary="   ",  # Whitespace only
            reasoning="Test",
        )
        assert response.summary == "Risk analysis completed"

    def test_summary_coercion_strips_whitespace(self):
        """Test summary strips leading/trailing whitespace."""
        response = LLMRiskResponse(
            risk_score=50,
            risk_level=RiskLevel.MEDIUM,
            summary="  Test summary  ",
            reasoning="Test",
        )
        assert response.summary == "Test summary"

    def test_reasoning_coercion_none_to_default(self):
        """Test None reasoning gets default value."""
        response = LLMRiskResponse(
            risk_score=50,
            risk_level=RiskLevel.MEDIUM,
            summary="Test",
            reasoning=None,  # type: ignore[arg-type]
        )
        assert response.reasoning == "No detailed reasoning provided"

    def test_reasoning_coercion_empty_string_to_default(self):
        """Test empty string reasoning gets default value."""
        response = LLMRiskResponse(
            risk_score=50,
            risk_level=RiskLevel.MEDIUM,
            summary="Test",
            reasoning="   ",
        )
        assert response.reasoning == "No detailed reasoning provided"

    def test_reasoning_coercion_strips_whitespace(self):
        """Test reasoning strips leading/trailing whitespace."""
        response = LLMRiskResponse(
            risk_score=50,
            risk_level=RiskLevel.MEDIUM,
            summary="Test",
            reasoning="  Test reasoning  ",
        )
        assert response.reasoning == "Test reasoning"

    def test_ensure_consistency_low_range(self):
        """Test consistency validator adjusts level for low scores (0-29)."""
        response = LLMRiskResponse(
            risk_score=15,
            risk_level=RiskLevel.HIGH,  # Inconsistent
            summary="Test",
            reasoning="Test",
        )
        # Should be corrected to LOW
        assert response.risk_level == RiskLevel.LOW

    def test_ensure_consistency_medium_range(self):
        """Test consistency validator adjusts level for medium scores (30-59)."""
        response = LLMRiskResponse(
            risk_score=45,
            risk_level=RiskLevel.LOW,  # Inconsistent
            summary="Test",
            reasoning="Test",
        )
        # Should be corrected to MEDIUM
        assert response.risk_level == RiskLevel.MEDIUM

    def test_ensure_consistency_high_range(self):
        """Test consistency validator adjusts level for high scores (60-84)."""
        response = LLMRiskResponse(
            risk_score=70,
            risk_level=RiskLevel.LOW,  # Inconsistent
            summary="Test",
            reasoning="Test",
        )
        # Should be corrected to HIGH
        assert response.risk_level == RiskLevel.HIGH

    def test_ensure_consistency_critical_range(self):
        """Test consistency validator adjusts level for critical scores (85-100)."""
        response = LLMRiskResponse(
            risk_score=90,
            risk_level=RiskLevel.MEDIUM,  # Inconsistent
            summary="Test",
            reasoning="Test",
        )
        # Should be corrected to CRITICAL
        assert response.risk_level == RiskLevel.CRITICAL

    def test_ensure_consistency_boundary_30(self):
        """Test consistency at boundary: score 30 should be MEDIUM."""
        response = LLMRiskResponse(
            risk_score=30,
            risk_level=RiskLevel.LOW,
            summary="Test",
            reasoning="Test",
        )
        assert response.risk_level == RiskLevel.MEDIUM

    def test_ensure_consistency_boundary_60(self):
        """Test consistency at boundary: score 60 should be HIGH."""
        response = LLMRiskResponse(
            risk_score=60,
            risk_level=RiskLevel.MEDIUM,
            summary="Test",
            reasoning="Test",
        )
        assert response.risk_level == RiskLevel.HIGH

    def test_ensure_consistency_boundary_85(self):
        """Test consistency at boundary: score 85 should be CRITICAL."""
        response = LLMRiskResponse(
            risk_score=85,
            risk_level=RiskLevel.HIGH,
            summary="Test",
            reasoning="Test",
        )
        assert response.risk_level == RiskLevel.CRITICAL

    def test_ensure_consistency_already_consistent(self):
        """Test consistency validator doesn't modify correct values."""
        response = LLMRiskResponse(
            risk_score=75,
            risk_level=RiskLevel.HIGH,
            summary="Test",
            reasoning="Test",
        )
        assert response.risk_level == RiskLevel.HIGH  # Should remain unchanged

    def test_entities_default_empty_list(self):
        """Test entities defaults to empty list."""
        response = LLMRiskResponse(
            risk_score=50,
            risk_level=RiskLevel.MEDIUM,
            summary="Test",
            reasoning="Test",
        )
        assert response.entities == []
        assert isinstance(response.entities, list)

    def test_entities_multiple_items(self):
        """Test entities can contain multiple items."""
        entities = [
            LLMEntity(type=EntityType.PERSON, description="Person 1"),
            LLMEntity(type=EntityType.VEHICLE, description="Car"),
            LLMEntity(type=EntityType.PET, description="Dog"),
        ]
        response = LLMRiskResponse(
            risk_score=50,
            risk_level=RiskLevel.MEDIUM,
            summary="Test",
            reasoning="Test",
            entities=entities,
        )
        assert len(response.entities) == 3
        assert response.entities[0].type == EntityType.PERSON

    def test_flags_default_empty_list(self):
        """Test flags defaults to empty list."""
        response = LLMRiskResponse(
            risk_score=50,
            risk_level=RiskLevel.MEDIUM,
            summary="Test",
            reasoning="Test",
        )
        assert response.flags == []
        assert isinstance(response.flags, list)

    def test_flags_multiple_items(self):
        """Test flags can contain multiple items."""
        flags = [
            LLMFlag(type=FlagType.VIOLENCE, description="Flag 1"),
            LLMFlag(type=FlagType.SUSPICIOUS_ATTIRE, description="Flag 2"),
        ]
        response = LLMRiskResponse(
            risk_score=75,
            risk_level=RiskLevel.HIGH,
            summary="Test",
            reasoning="Test",
            flags=flags,
        )
        assert len(response.flags) == 2

    def test_recommended_action_optional(self):
        """Test recommended_action is optional and defaults to None."""
        response = LLMRiskResponse(
            risk_score=50,
            risk_level=RiskLevel.MEDIUM,
            summary="Test",
            reasoning="Test",
        )
        assert response.recommended_action is None

    def test_recommended_action_with_value(self):
        """Test recommended_action accepts string value."""
        response = LLMRiskResponse(
            risk_score=80,
            risk_level=RiskLevel.HIGH,
            summary="Test",
            reasoning="Test",
            recommended_action="Activate lights and notify homeowner",
        )
        assert response.recommended_action == "Activate lights and notify homeowner"

    def test_confidence_factors_optional(self):
        """Test confidence_factors is optional and defaults to None."""
        response = LLMRiskResponse(
            risk_score=50,
            risk_level=RiskLevel.MEDIUM,
            summary="Test",
            reasoning="Test",
        )
        assert response.confidence_factors is None

    def test_allows_extra_fields(self):
        """Test response allows extra fields from LLM."""
        data = {
            "risk_score": 50,
            "risk_level": "medium",
            "summary": "Test",
            "reasoning": "Test",
            "extra_llm_field": "extra_value",
            "another_field": 123,
        }
        response = LLMRiskResponse.model_validate(data)
        assert response.risk_score == 50

    def test_to_dict_method(self):
        """Test to_dict returns dict with core fields only."""
        response = LLMRiskResponse(
            risk_score=75,
            risk_level=RiskLevel.HIGH,
            summary="Test summary",
            reasoning="Test reasoning",
            entities=[LLMEntity(type=EntityType.PERSON, description="Person")],
            flags=[LLMFlag(type=FlagType.VIOLENCE, description="Flag")],
        )
        data = response.to_dict()

        # Should only include core fields
        assert data == {
            "risk_score": 75,
            "risk_level": "high",
            "summary": "Test summary",
            "reasoning": "Test reasoning",
        }
        # Entities and flags should not be included
        assert "entities" not in data
        assert "flags" not in data

    def test_model_dump_includes_all_fields(self):
        """Test model_dump includes all fields (vs to_dict which filters)."""
        response = LLMRiskResponse(
            risk_score=75,
            risk_level=RiskLevel.HIGH,
            summary="Test",
            reasoning="Test",
            entities=[LLMEntity(type=EntityType.PERSON, description="Person")],
        )
        data = response.model_dump()

        assert "risk_score" in data
        assert "entities" in data
        assert len(data["entities"]) == 1

    def test_serialization_with_nested_models(self):
        """Test complete serialization with nested entities, flags, and confidence."""
        response = LLMRiskResponse(
            risk_score=80,
            risk_level=RiskLevel.HIGH,
            summary="High risk event",
            reasoning="Multiple threats",
            entities=[
                LLMEntity(
                    type=EntityType.PERSON,
                    description="Suspicious person",
                    threat_level=ThreatLevel.HIGH,
                )
            ],
            flags=[
                LLMFlag(
                    type=FlagType.SUSPICIOUS_ATTIRE,
                    description="Masked face",
                    severity=FlagSeverity.ALERT,
                )
            ],
            confidence_factors=LLMConfidenceFactors(
                detection_quality=DetectionQuality.GOOD,
                weather_impact=WeatherImpact.NONE,
                enrichment_coverage=EnrichmentCoverage.FULL,
            ),
        )

        data = response.model_dump()

        assert data["risk_score"] == 80
        assert data["entities"][0]["type"] == "person"
        assert data["flags"][0]["severity"] == "alert"
        assert data["confidence_factors"]["detection_quality"] == "good"


class TestValidateLLMResponse:
    """Tests for validate_llm_response helper function."""

    def test_validate_valid_response(self):
        """Test validating valid LLM response data."""
        data = {
            "risk_score": 65,
            "risk_level": "high",
            "summary": "Activity detected",
            "reasoning": "Multiple persons observed",
        }
        result = validate_llm_response(data)

        assert isinstance(result, LLMRiskResponse)
        assert result.risk_score == 65
        assert result.risk_level == RiskLevel.HIGH

    def test_validate_response_with_all_fields(self):
        """Test validating response with all optional fields."""
        data = {
            "risk_score": 75,
            "risk_level": "high",
            "summary": "Test",
            "reasoning": "Test",
            "entities": [{"type": "person", "description": "Person 1", "threat_level": "high"}],
            "flags": [
                {
                    "type": "suspicious_attire",
                    "description": "Flag",
                    "severity": "alert",
                }
            ],
            "recommended_action": "Notify homeowner",
            "confidence_factors": {
                "detection_quality": "good",
                "weather_impact": "none",
                "enrichment_coverage": "full",
            },
        }
        result = validate_llm_response(data)

        assert len(result.entities) == 1
        assert len(result.flags) == 1
        assert result.confidence_factors is not None

    def test_validate_response_missing_required_field(self):
        """Test validation fails with clear error for missing required field."""
        data = {
            "risk_score": 50,
            # Missing risk_level
            "summary": "Test",
            "reasoning": "Test",
        }

        with pytest.raises(LLMResponseParseError) as exc_info:
            validate_llm_response(data)

        error = exc_info.value
        assert "risk_level" in error.message
        assert error.raw_response is not None

    def test_validate_response_invalid_field_type(self):
        """Test validation fails with clear error for invalid field type."""
        data = {
            "risk_score": "not_a_valid_number",  # Invalid
            "risk_level": "high",
            "summary": "Test",
            "reasoning": "Test",
        }

        with pytest.raises(LLMResponseParseError) as exc_info:
            validate_llm_response(data)

        error = exc_info.value
        assert "risk_score" in error.message

    def test_validate_response_multiple_errors(self):
        """Test validation error message includes multiple field errors."""
        data = {
            "risk_score": "invalid",
            "risk_level": "invalid_level",
            # Missing summary
            "reasoning": "Test",
        }

        with pytest.raises(LLMResponseParseError) as exc_info:
            validate_llm_response(data)

        error = exc_info.value
        # Should mention multiple errors
        assert "risk_score" in error.message or "risk_level" in error.message

    def test_validate_response_truncates_long_raw_response(self):
        """Test raw_response is truncated to 500 chars for safety."""
        data = {
            "risk_score": 50,
            # Missing risk_level
            "summary": "Test",
            "reasoning": "Test",
            "extra_long_field": "x" * 1000,  # Very long field
        }

        with pytest.raises(LLMResponseParseError) as exc_info:
            validate_llm_response(data)

        error = exc_info.value
        assert error.raw_response is not None
        assert len(error.raw_response) <= 500


class TestInferRiskLevelFromScore:
    """Tests for infer_risk_level_from_score helper function."""

    def test_infer_low_boundary_0(self):
        """Test score 0 infers LOW."""
        assert infer_risk_level_from_score(0) == RiskLevel.LOW

    def test_infer_low_boundary_29(self):
        """Test score 29 infers LOW."""
        assert infer_risk_level_from_score(29) == RiskLevel.LOW

    def test_infer_low_mid_range(self):
        """Test mid-range low score infers LOW."""
        assert infer_risk_level_from_score(15) == RiskLevel.LOW

    def test_infer_medium_boundary_30(self):
        """Test score 30 infers MEDIUM."""
        assert infer_risk_level_from_score(30) == RiskLevel.MEDIUM

    def test_infer_medium_boundary_59(self):
        """Test score 59 infers MEDIUM."""
        assert infer_risk_level_from_score(59) == RiskLevel.MEDIUM

    def test_infer_medium_mid_range(self):
        """Test mid-range medium score infers MEDIUM."""
        assert infer_risk_level_from_score(45) == RiskLevel.MEDIUM

    def test_infer_high_boundary_60(self):
        """Test score 60 infers HIGH."""
        assert infer_risk_level_from_score(60) == RiskLevel.HIGH

    def test_infer_high_boundary_84(self):
        """Test score 84 infers HIGH."""
        assert infer_risk_level_from_score(84) == RiskLevel.HIGH

    def test_infer_high_mid_range(self):
        """Test mid-range high score infers HIGH."""
        assert infer_risk_level_from_score(75) == RiskLevel.HIGH

    def test_infer_critical_boundary_85(self):
        """Test score 85 infers CRITICAL."""
        assert infer_risk_level_from_score(85) == RiskLevel.CRITICAL

    def test_infer_critical_boundary_100(self):
        """Test score 100 infers CRITICAL."""
        assert infer_risk_level_from_score(100) == RiskLevel.CRITICAL

    def test_infer_critical_mid_range(self):
        """Test mid-range critical score infers CRITICAL."""
        assert infer_risk_level_from_score(92) == RiskLevel.CRITICAL

    def test_infer_all_boundaries(self):
        """Test all boundary transitions."""
        assert infer_risk_level_from_score(29) == RiskLevel.LOW
        assert infer_risk_level_from_score(30) == RiskLevel.MEDIUM
        assert infer_risk_level_from_score(59) == RiskLevel.MEDIUM
        assert infer_risk_level_from_score(60) == RiskLevel.HIGH
        assert infer_risk_level_from_score(84) == RiskLevel.HIGH
        assert infer_risk_level_from_score(85) == RiskLevel.CRITICAL


class TestLLMResponseParseError:
    """Tests for LLMResponseParseError exception class."""

    def test_error_with_message_only(self):
        """Test creating error with message only."""
        error = LLMResponseParseError("Test error message")
        assert str(error) == "Test error message"
        assert error.message == "Test error message"
        assert error.raw_response is None

    def test_error_with_message_and_raw_response(self):
        """Test creating error with message and raw response."""
        raw = '{"risk_score": "invalid"}'
        error = LLMResponseParseError("Validation failed", raw_response=raw)

        assert error.message == "Validation failed"
        assert error.raw_response == raw

    def test_error_inherits_from_exception(self):
        """Test error is a proper Exception subclass."""
        error = LLMResponseParseError("Test")
        assert isinstance(error, Exception)

    def test_error_can_be_raised_and_caught(self):
        """Test error can be raised and caught normally."""
        with pytest.raises(LLMResponseParseError) as exc_info:
            raise LLMResponseParseError("Test error", raw_response="raw data")

        caught_error = exc_info.value
        assert caught_error.message == "Test error"
        assert caught_error.raw_response == "raw data"

    def test_error_attributes_accessible(self):
        """Test error attributes are accessible after catching."""
        try:
            raise LLMResponseParseError("Parsing failed", raw_response='{"data": 1}')
        except LLMResponseParseError as e:
            assert e.message == "Parsing failed"
            assert e.raw_response == '{"data": 1}'
            assert "Parsing failed" in str(e)
