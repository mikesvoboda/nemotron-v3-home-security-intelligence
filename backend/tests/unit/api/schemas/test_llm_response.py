"""Unit tests for LLM response Pydantic schemas.

These tests cover the LLM response validation schemas including:
- LLMRiskResponse: Risk assessment response from Nemotron
- LLMRawResponse: Raw parsed response before validation
- RiskEntity: Entity identified in the risk analysis
- RiskFlag: Risk flags with severity levels
- ConfidenceFactors: Factors affecting confidence in the analysis
"""

import pytest
from pydantic import ValidationError

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


class TestLLMRiskResponse:
    """Tests for the LLMRiskResponse schema."""

    def test_valid_response_all_fields(self):
        """Test valid response with all fields provided."""
        from backend.api.schemas.llm_response import LLMRiskResponse

        response = LLMRiskResponse(
            risk_score=75,
            risk_level="high",
            summary="Suspicious activity detected at front entrance",
            reasoning="Person detected at unusual time with unknown vehicle present",
        )

        assert response.risk_score == 75
        assert response.risk_level == "high"
        assert "Suspicious activity" in response.summary
        assert "Person detected" in response.reasoning

    def test_valid_response_minimum_fields(self):
        """Test valid response with only required fields."""
        from backend.api.schemas.llm_response import LLMRiskResponse

        response = LLMRiskResponse(
            risk_score=50,
            risk_level="medium",
            summary="Normal activity",
            reasoning="Routine daytime activity",
        )

        assert response.risk_score == 50
        assert response.risk_level == "medium"

    def test_risk_score_boundary_zero(self):
        """Test risk_score at lower boundary (0)."""
        from backend.api.schemas.llm_response import LLMRiskResponse

        response = LLMRiskResponse(
            risk_score=0,
            risk_level="low",
            summary="No activity",
            reasoning="Clear",
        )

        assert response.risk_score == 0

    def test_risk_score_boundary_hundred(self):
        """Test risk_score at upper boundary (100)."""
        from backend.api.schemas.llm_response import LLMRiskResponse

        response = LLMRiskResponse(
            risk_score=100,
            risk_level="critical",
            summary="Emergency",
            reasoning="Immediate threat",
        )

        assert response.risk_score == 100

    def test_risk_score_below_zero_fails(self):
        """Test risk_score below 0 raises validation error."""
        from backend.api.schemas.llm_response import LLMRiskResponse

        with pytest.raises(ValidationError) as exc_info:
            LLMRiskResponse(
                risk_score=-1,
                risk_level="low",
                summary="Test",
                reasoning="Test",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("risk_score",) for e in errors)

    def test_risk_score_above_hundred_fails(self):
        """Test risk_score above 100 raises validation error."""
        from backend.api.schemas.llm_response import LLMRiskResponse

        with pytest.raises(ValidationError) as exc_info:
            LLMRiskResponse(
                risk_score=101,
                risk_level="critical",
                summary="Test",
                reasoning="Test",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("risk_score",) for e in errors)

    def test_invalid_risk_level_fails(self):
        """Test invalid risk_level raises validation error."""
        from backend.api.schemas.llm_response import LLMRiskResponse

        with pytest.raises(ValidationError) as exc_info:
            LLMRiskResponse(
                risk_score=50,
                risk_level="invalid_level",
                summary="Test",
                reasoning="Test",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("risk_level",) for e in errors)

    def test_valid_risk_levels(self):
        """Test all valid risk levels are accepted."""
        from backend.api.schemas.llm_response import LLMRiskResponse

        valid_levels = ["low", "medium", "high", "critical"]

        for level in valid_levels:
            response = LLMRiskResponse(
                risk_score=50,
                risk_level=level,
                summary="Test",
                reasoning="Test",
            )
            assert response.risk_level == level

    def test_risk_level_case_normalization(self):
        """Test that risk_level is normalized to lowercase."""
        from backend.api.schemas.llm_response import LLMRiskResponse

        # Test uppercase
        response = LLMRiskResponse(
            risk_score=75,
            risk_level="HIGH",
            summary="Test",
            reasoning="Test",
        )
        assert response.risk_level == "high"

        # Test mixed case
        response2 = LLMRiskResponse(
            risk_score=50,
            risk_level="Medium",
            summary="Test",
            reasoning="Test",
        )
        assert response2.risk_level == "medium"

    def test_missing_risk_score_fails(self):
        """Test missing risk_score raises validation error."""
        from backend.api.schemas.llm_response import LLMRiskResponse

        with pytest.raises(ValidationError) as exc_info:
            LLMRiskResponse(
                risk_level="high",
                summary="Test",
                reasoning="Test",
            )  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("risk_score",) for e in errors)

    def test_missing_risk_level_fails(self):
        """Test missing risk_level raises validation error."""
        from backend.api.schemas.llm_response import LLMRiskResponse

        with pytest.raises(ValidationError) as exc_info:
            LLMRiskResponse(
                risk_score=50,
                summary="Test",
                reasoning="Test",
            )  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("risk_level",) for e in errors)

    def test_missing_summary_fails(self):
        """Test missing summary raises validation error."""
        from backend.api.schemas.llm_response import LLMRiskResponse

        with pytest.raises(ValidationError) as exc_info:
            LLMRiskResponse(
                risk_score=50,
                risk_level="medium",
                reasoning="Test",
            )  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("summary",) for e in errors)

    def test_missing_reasoning_fails(self):
        """Test missing reasoning raises validation error."""
        from backend.api.schemas.llm_response import LLMRiskResponse

        with pytest.raises(ValidationError) as exc_info:
            LLMRiskResponse(
                risk_score=50,
                risk_level="medium",
                summary="Test",
            )  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("reasoning",) for e in errors)

    def test_model_validate_from_dict(self):
        """Test model_validate works with dictionary input."""
        from backend.api.schemas.llm_response import LLMRiskResponse

        data = {
            "risk_score": 65,
            "risk_level": "high",
            "summary": "Activity detected",
            "reasoning": "Multiple persons observed",
        }

        response = LLMRiskResponse.model_validate(data)

        assert response.risk_score == 65
        assert response.risk_level == "high"

    def test_model_validate_with_extra_fields(self):
        """Test model_validate ignores extra fields from LLM response."""
        from backend.api.schemas.llm_response import LLMRiskResponse

        data = {
            "risk_score": 50,
            "risk_level": "medium",
            "summary": "Test",
            "reasoning": "Test",
            "extra_field": "should be ignored",
            "another_extra": 123,
        }

        # Should not raise
        response = LLMRiskResponse.model_validate(data)

        assert response.risk_score == 50
        # Extra fields should not be accessible
        assert not hasattr(response, "extra_field")

    def test_model_dump(self):
        """Test model_dump returns correct dictionary."""
        from backend.api.schemas.llm_response import LLMRiskResponse

        response = LLMRiskResponse(
            risk_score=80,
            risk_level="high",
            summary="High risk activity",
            reasoning="Detailed reasoning",
        )

        data = response.model_dump()

        assert data["risk_score"] == 80
        assert data["risk_level"] == "high"
        assert data["summary"] == "High risk activity"
        assert data["reasoning"] == "Detailed reasoning"

    def test_risk_score_float_converted_to_int(self):
        """Test that float risk_score is converted to int."""
        from backend.api.schemas.llm_response import LLMRiskResponse

        response = LLMRiskResponse(
            risk_score=75.5,  # type: ignore[arg-type]
            risk_level="high",
            summary="Test",
            reasoning="Test",
        )

        assert response.risk_score == 75
        assert isinstance(response.risk_score, int)

    def test_risk_score_string_number_converted(self):
        """Test that string number risk_score is converted to int."""
        from backend.api.schemas.llm_response import LLMRiskResponse

        response = LLMRiskResponse(
            risk_score="60",  # type: ignore[arg-type]
            risk_level="high",
            summary="Test",
            reasoning="Test",
        )

        assert response.risk_score == 60
        assert isinstance(response.risk_score, int)

    def test_risk_score_invalid_string_fails(self):
        """Test that non-numeric string risk_score fails."""
        from backend.api.schemas.llm_response import LLMRiskResponse

        with pytest.raises(ValidationError) as exc_info:
            LLMRiskResponse(
                risk_score="not_a_number",  # type: ignore[arg-type]
                risk_level="medium",
                summary="Test",
                reasoning="Test",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("risk_score",) for e in errors)


class TestLLMRawResponse:
    """Tests for the LLMRawResponse schema (pre-validation parsing)."""

    def test_valid_raw_response(self):
        """Test valid raw response with all optional fields."""
        from backend.api.schemas.llm_response import LLMRawResponse

        response = LLMRawResponse(
            risk_score=75,
            risk_level="high",
            summary="Test summary",
            reasoning="Test reasoning",
        )

        assert response.risk_score == 75
        assert response.risk_level == "high"
        assert response.summary == "Test summary"
        assert response.reasoning == "Test reasoning"

    def test_raw_response_optional_fields(self):
        """Test raw response with only risk_score and risk_level."""
        from backend.api.schemas.llm_response import LLMRawResponse

        response = LLMRawResponse(
            risk_score=50,
            risk_level="medium",
        )

        assert response.risk_score == 50
        assert response.risk_level == "medium"
        assert response.summary is None
        assert response.reasoning is None

    def test_raw_response_no_score_validation(self):
        """Test raw response allows scores outside 0-100 range."""
        from backend.api.schemas.llm_response import LLMRawResponse

        # Should not raise for out-of-range scores
        response = LLMRawResponse(
            risk_score=150,
            risk_level="high",
        )

        assert response.risk_score == 150

        response2 = LLMRawResponse(
            risk_score=-50,
            risk_level="low",
        )

        assert response2.risk_score == -50

    def test_raw_response_allows_invalid_risk_level(self):
        """Test raw response allows invalid risk levels for graceful handling."""
        from backend.api.schemas.llm_response import LLMRawResponse

        response = LLMRawResponse(
            risk_score=50,
            risk_level="invalid_level",
        )

        assert response.risk_level == "invalid_level"

    def test_raw_response_model_validate_from_llm(self):
        """Test model_validate with typical LLM JSON output."""
        from backend.api.schemas.llm_response import LLMRawResponse

        llm_json = {
            "risk_score": 72,
            "risk_level": "HIGH",
            "summary": "Multiple persons detected",
            "reasoning": "Activity at unusual hour",
        }

        response = LLMRawResponse.model_validate(llm_json)

        assert response.risk_score == 72
        assert response.risk_level == "HIGH"  # Not normalized in raw response

    def test_raw_response_with_extra_llm_fields(self):
        """Test raw response ignores extra fields LLM might return."""
        from backend.api.schemas.llm_response import LLMRawResponse

        llm_json = {
            "risk_score": 50,
            "risk_level": "medium",
            "summary": "Test",
            "reasoning": "Test",
            "threats": ["unknown person"],  # Extra field
            "recommended_actions": ["review footage"],  # Extra field
            "confidence": {"overall": 0.95},  # NEM-3606: Now uses structured confidence
        }

        response = LLMRawResponse.model_validate(llm_json)

        assert response.risk_score == 50

    def test_raw_response_missing_required_fields_fails(self):
        """Test raw response fails when risk_score and risk_level are missing."""
        from backend.api.schemas.llm_response import LLMRawResponse

        with pytest.raises(ValidationError):
            LLMRawResponse.model_validate({"summary": "Test"})


class TestLLMResponseValidation:
    """Integration tests for LLM response validation flow."""

    def test_validate_raw_then_normalize(self):
        """Test workflow: parse raw response then normalize to validated response."""
        from backend.api.schemas.llm_response import LLMRawResponse

        # Simulate raw LLM output
        raw_json = {
            "risk_score": 150,  # Out of range
            "risk_level": "EXTREME",  # Invalid level
            "summary": "Test summary",
            "reasoning": "Test reasoning",
        }

        # First parse as raw (lenient)
        raw = LLMRawResponse.model_validate(raw_json)
        assert raw.risk_score == 150
        assert raw.risk_level == "EXTREME"

        # Then normalize to validated response (this would fail without normalization)
        # The nemotron_analyzer._validate_risk_data handles this normalization

    def test_to_validated_response_happy_path(self):
        """Test to_validated_response method for valid data."""
        from backend.api.schemas.llm_response import LLMRawResponse, RiskLevel

        raw = LLMRawResponse(
            risk_score=75,
            risk_level="high",
            summary="Activity detected",
            reasoning="Person at entrance",
        )

        validated = raw.to_validated_response()

        assert validated.risk_score == 75
        assert validated.risk_level == RiskLevel.HIGH.value
        assert validated.summary == "Activity detected"
        assert validated.reasoning == "Person at entrance"

    def test_to_validated_response_clamps_score(self):
        """Test to_validated_response clamps risk_score to 0-100."""
        from backend.api.schemas.llm_response import LLMRawResponse

        # Test upper bound
        raw_high = LLMRawResponse(
            risk_score=150,
            risk_level="high",
            summary="Test",
            reasoning="Test",
        )
        validated = raw_high.to_validated_response()
        assert validated.risk_score == 100

        # Test lower bound
        raw_low = LLMRawResponse(
            risk_score=-50,
            risk_level="low",
            summary="Test",
            reasoning="Test",
        )
        validated = raw_low.to_validated_response()
        assert validated.risk_score == 0

    def test_to_validated_response_normalizes_risk_level(self):
        """Test to_validated_response normalizes risk_level to lowercase."""
        from backend.api.schemas.llm_response import LLMRawResponse

        raw = LLMRawResponse(
            risk_score=75,
            risk_level="HIGH",
            summary="Test",
            reasoning="Test",
        )

        validated = raw.to_validated_response()
        assert validated.risk_level == "high"

    def test_to_validated_response_infers_risk_level(self):
        """Test to_validated_response infers risk_level from score when invalid."""
        from backend.api.schemas.llm_response import LLMRawResponse

        # Invalid level should be inferred from score
        raw = LLMRawResponse(
            risk_score=90,
            risk_level="invalid_level",
            summary="Test",
            reasoning="Test",
        )

        validated = raw.to_validated_response()
        assert validated.risk_level == "critical"  # 90 -> critical

    def test_to_validated_response_provides_defaults(self):
        """Test to_validated_response provides defaults for missing fields."""
        from backend.api.schemas.llm_response import LLMRawResponse

        raw = LLMRawResponse(
            risk_score=50,
            risk_level="medium",
            summary=None,
            reasoning=None,
        )

        validated = raw.to_validated_response()
        assert validated.summary is not None
        assert validated.reasoning is not None
        assert "analysis" in validated.summary.lower() or len(validated.summary) > 0
        assert len(validated.reasoning) > 0

    def test_to_validated_response_none_score_defaults_to_50(self):
        """Test to_validated_response defaults None score to 50."""
        from backend.api.schemas.llm_response import LLMRawResponse

        raw = LLMRawResponse(
            risk_score=None,
            risk_level="medium",
        )

        validated = raw.to_validated_response()
        assert validated.risk_score == 50

    def test_risk_level_boundary_inference_low(self):
        """Test risk level inference for low scores (0-29)."""
        from backend.api.schemas.llm_response import LLMRawResponse

        for score in [0, 15, 29]:
            raw = LLMRawResponse(risk_score=score, risk_level="invalid")
            validated = raw.to_validated_response()
            assert validated.risk_level == "low", f"Score {score} should map to low"

    def test_risk_level_boundary_inference_medium(self):
        """Test risk level inference for medium scores (30-59)."""
        from backend.api.schemas.llm_response import LLMRawResponse

        for score in [30, 45, 59]:
            raw = LLMRawResponse(risk_score=score, risk_level="invalid")
            validated = raw.to_validated_response()
            assert validated.risk_level == "medium", f"Score {score} should map to medium"

    def test_risk_level_boundary_inference_high(self):
        """Test risk level inference for high scores (60-84)."""
        from backend.api.schemas.llm_response import LLMRawResponse

        for score in [60, 75, 84]:
            raw = LLMRawResponse(risk_score=score, risk_level="invalid")
            validated = raw.to_validated_response()
            assert validated.risk_level == "high", f"Score {score} should map to high"

    def test_risk_level_boundary_inference_critical(self):
        """Test risk level inference for critical scores (85-100)."""
        from backend.api.schemas.llm_response import LLMRawResponse

        for score in [85, 92, 100]:
            raw = LLMRawResponse(risk_score=score, risk_level="invalid")
            validated = raw.to_validated_response()
            assert validated.risk_level == "critical", f"Score {score} should map to critical"


class TestRiskEntity:
    """Tests for the RiskEntity schema (NEM-3601)."""

    def test_valid_risk_entity(self):
        """Test valid RiskEntity with all fields."""
        from backend.api.schemas.llm_response import RiskEntity

        entity = RiskEntity(
            type="person",
            description="Unknown individual near front entrance",
            threat_level="medium",
        )

        assert entity.type == "person"
        assert entity.description == "Unknown individual near front entrance"
        assert entity.threat_level == "medium"

    def test_valid_threat_levels(self):
        """Test all valid threat levels are accepted."""
        from backend.api.schemas.llm_response import RiskEntity

        for level in ["low", "medium", "high"]:
            entity = RiskEntity(
                type="vehicle",
                description="Test",
                threat_level=level,
            )
            assert entity.threat_level == level

    def test_invalid_threat_level_fails(self):
        """Test invalid threat_level raises validation error."""
        from backend.api.schemas.llm_response import RiskEntity

        with pytest.raises(ValidationError) as exc_info:
            RiskEntity(
                type="person",
                description="Test",
                threat_level="critical",  # Invalid - not in enum
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("threat_level",) for e in errors)

    def test_missing_required_fields_fails(self):
        """Test missing required fields raise validation error."""
        from backend.api.schemas.llm_response import RiskEntity

        with pytest.raises(ValidationError):
            RiskEntity(type="person")  # type: ignore[call-arg]


class TestRiskFlag:
    """Tests for the RiskFlag schema (NEM-3601)."""

    def test_valid_risk_flag(self):
        """Test valid RiskFlag with all fields."""
        from backend.api.schemas.llm_response import RiskFlag

        flag = RiskFlag(
            type="loitering",
            description="Person has been stationary for extended period",
            severity="warning",
        )

        assert flag.type == "loitering"
        assert flag.description == "Person has been stationary for extended period"
        assert flag.severity == "warning"

    def test_valid_severities(self):
        """Test all valid severities are accepted."""
        from backend.api.schemas.llm_response import RiskFlag

        for severity in ["warning", "alert", "critical"]:
            flag = RiskFlag(
                type="test_flag",
                description="Test",
                severity=severity,
            )
            assert flag.severity == severity

    def test_invalid_severity_fails(self):
        """Test invalid severity raises validation error."""
        from backend.api.schemas.llm_response import RiskFlag

        with pytest.raises(ValidationError) as exc_info:
            RiskFlag(
                type="test",
                description="Test",
                severity="low",  # Invalid - not in enum
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("severity",) for e in errors)


class TestConfidenceFactors:
    """Tests for the ConfidenceFactors schema (NEM-3601)."""

    def test_default_confidence_factors(self):
        """Test ConfidenceFactors with default values."""
        from backend.api.schemas.llm_response import ConfidenceFactors

        factors = ConfidenceFactors()

        assert factors.detection_quality == "good"
        assert factors.weather_impact == "none"
        assert factors.enrichment_coverage == "full"

    def test_custom_confidence_factors(self):
        """Test ConfidenceFactors with custom values."""
        from backend.api.schemas.llm_response import ConfidenceFactors

        factors = ConfidenceFactors(
            detection_quality="poor",
            weather_impact="significant",
            enrichment_coverage="minimal",
        )

        assert factors.detection_quality == "poor"
        assert factors.weather_impact == "significant"
        assert factors.enrichment_coverage == "minimal"

    def test_valid_detection_quality_values(self):
        """Test all valid detection_quality values."""
        from backend.api.schemas.llm_response import ConfidenceFactors

        for quality in ["good", "fair", "poor"]:
            factors = ConfidenceFactors(detection_quality=quality)
            assert factors.detection_quality == quality

    def test_valid_weather_impact_values(self):
        """Test all valid weather_impact values."""
        from backend.api.schemas.llm_response import ConfidenceFactors

        for impact in ["none", "minor", "significant"]:
            factors = ConfidenceFactors(weather_impact=impact)
            assert factors.weather_impact == impact

    def test_valid_enrichment_coverage_values(self):
        """Test all valid enrichment_coverage values."""
        from backend.api.schemas.llm_response import ConfidenceFactors

        for coverage in ["full", "partial", "minimal"]:
            factors = ConfidenceFactors(enrichment_coverage=coverage)
            assert factors.enrichment_coverage == coverage

    def test_invalid_detection_quality_fails(self):
        """Test invalid detection_quality raises validation error."""
        from backend.api.schemas.llm_response import ConfidenceFactors

        with pytest.raises(ValidationError) as exc_info:
            ConfidenceFactors(detection_quality="excellent")

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("detection_quality",) for e in errors)


class TestLLMRiskResponseAdvancedFields:
    """Tests for advanced fields in LLMRiskResponse (NEM-3601)."""

    def test_response_with_entities(self):
        """Test LLMRiskResponse with entities list."""
        from backend.api.schemas.llm_response import LLMRiskResponse, RiskEntity

        response = LLMRiskResponse(
            risk_score=75,
            risk_level="high",
            summary="Suspicious activity detected",
            reasoning="Unknown person near entrance",
            entities=[
                RiskEntity(
                    type="person",
                    description="Unknown individual",
                    threat_level="medium",
                )
            ],
        )

        assert len(response.entities) == 1
        assert response.entities[0].type == "person"

    def test_response_with_flags(self):
        """Test LLMRiskResponse with flags list."""
        from backend.api.schemas.llm_response import LLMRiskResponse, RiskFlag

        response = LLMRiskResponse(
            risk_score=65,
            risk_level="high",
            summary="Person loitering",
            reasoning="Extended stationary period",
            flags=[
                RiskFlag(
                    type="loitering",
                    description="Stationary for 5+ minutes",
                    severity="warning",
                )
            ],
        )

        assert len(response.flags) == 1
        assert response.flags[0].type == "loitering"

    def test_response_with_recommended_action(self):
        """Test LLMRiskResponse with recommended_action."""
        from backend.api.schemas.llm_response import LLMRiskResponse

        response = LLMRiskResponse(
            risk_score=85,
            risk_level="critical",
            summary="Potential threat detected",
            reasoning="Armed individual identified",
            recommended_action="Contact authorities immediately",
        )

        assert response.recommended_action == "Contact authorities immediately"

    def test_response_with_confidence_factors(self):
        """Test LLMRiskResponse with confidence_factors."""
        from backend.api.schemas.llm_response import ConfidenceFactors, LLMRiskResponse

        response = LLMRiskResponse(
            risk_score=50,
            risk_level="medium",
            summary="Activity detected",
            reasoning="Normal activity",
            confidence_factors=ConfidenceFactors(
                detection_quality="fair",
                weather_impact="minor",
                enrichment_coverage="partial",
            ),
        )

        assert response.confidence_factors is not None
        assert response.confidence_factors.detection_quality == "fair"

    def test_response_with_all_advanced_fields(self):
        """Test LLMRiskResponse with all advanced fields populated."""
        from backend.api.schemas.llm_response import (
            ConfidenceFactors,
            LLMRiskResponse,
            RiskEntity,
            RiskFlag,
        )

        response = LLMRiskResponse(
            risk_score=90,
            risk_level="critical",
            summary="Multiple threats detected",
            reasoning="Detailed analysis",
            entities=[
                RiskEntity(type="person", description="Unknown", threat_level="high"),
                RiskEntity(type="vehicle", description="Unmarked van", threat_level="medium"),
            ],
            flags=[
                RiskFlag(
                    type="weapon_detected", description="Possible weapon", severity="critical"
                ),
                RiskFlag(type="nighttime_activity", description="Late hour", severity="warning"),
            ],
            recommended_action="Review footage and contact security",
            confidence_factors=ConfidenceFactors(
                detection_quality="good",
                weather_impact="none",
                enrichment_coverage="full",
            ),
        )

        assert len(response.entities) == 2
        assert len(response.flags) == 2
        assert response.recommended_action is not None
        assert response.confidence_factors is not None

    def test_response_defaults_for_advanced_fields(self):
        """Test that advanced fields default to empty/None appropriately."""
        from backend.api.schemas.llm_response import LLMRiskResponse

        response = LLMRiskResponse(
            risk_score=50,
            risk_level="medium",
            summary="Test",
            reasoning="Test",
        )

        assert response.entities == []
        assert response.flags == []
        assert response.recommended_action is None
        assert response.confidence_factors is None

    def test_model_dump_includes_advanced_fields(self):
        """Test model_dump includes advanced fields."""
        from backend.api.schemas.llm_response import (
            ConfidenceFactors,
            LLMRiskResponse,
            RiskEntity,
            RiskFlag,
        )

        response = LLMRiskResponse(
            risk_score=75,
            risk_level="high",
            summary="Test",
            reasoning="Test",
            entities=[RiskEntity(type="person", description="Test", threat_level="low")],
            flags=[RiskFlag(type="test", description="Test", severity="warning")],
            recommended_action="Review",
            confidence_factors=ConfidenceFactors(),
        )

        data = response.model_dump()

        assert "entities" in data
        assert "flags" in data
        assert "recommended_action" in data
        assert "confidence_factors" in data
        assert len(data["entities"]) == 1
        assert len(data["flags"]) == 1


class TestLLMRawResponseAdvancedFields:
    """Tests for advanced fields in LLMRawResponse (NEM-3601)."""

    def test_raw_response_with_advanced_fields(self):
        """Test LLMRawResponse parses advanced fields from LLM output."""
        from backend.api.schemas.llm_response import LLMRawResponse

        llm_json = {
            "risk_score": 80,
            "risk_level": "high",
            "summary": "Multiple threats",
            "reasoning": "Analysis",
            "entities": [{"type": "person", "description": "Unknown", "threat_level": "high"}],
            "flags": [{"type": "weapon", "description": "Possible weapon", "severity": "critical"}],
            "recommended_action": "Contact police",
            "confidence_factors": {
                "detection_quality": "good",
                "weather_impact": "none",
                "enrichment_coverage": "full",
            },
        }

        response = LLMRawResponse.model_validate(llm_json)

        assert response.risk_score == 80
        assert len(response.entities) == 1
        assert len(response.flags) == 1
        assert response.recommended_action == "Contact police"
        assert response.confidence_factors is not None

    def test_raw_response_to_validated_preserves_advanced_fields(self):
        """Test to_validated_response preserves advanced fields."""
        from backend.api.schemas.llm_response import LLMRawResponse

        raw = LLMRawResponse(
            risk_score=75,
            risk_level="high",
            summary="Test",
            reasoning="Test",
            entities=[{"type": "person", "description": "Test", "threat_level": "medium"}],
            flags=[{"type": "test", "description": "Test", "severity": "warning"}],
            recommended_action="Review footage",
            confidence_factors={
                "detection_quality": "fair",
                "weather_impact": "minor",
                "enrichment_coverage": "partial",
            },
        )

        validated = raw.to_validated_response()

        assert len(validated.entities) == 1
        assert validated.entities[0].type == "person"
        assert len(validated.flags) == 1
        assert validated.flags[0].type == "test"
        assert validated.recommended_action == "Review footage"
        assert validated.confidence_factors is not None
        assert validated.confidence_factors.detection_quality == "fair"

    def test_raw_response_handles_invalid_entity_gracefully(self):
        """Test raw response handles invalid entity data gracefully."""
        from backend.api.schemas.llm_response import LLMRawResponse

        # Entity with invalid threat_level
        raw = LLMRawResponse(
            risk_score=50,
            risk_level="medium",
            entities=[{"type": "person", "description": "Test", "threat_level": "extreme"}],
        )

        validated = raw.to_validated_response()
        # Invalid entities should be filtered out
        assert validated.entities == []

    def test_raw_response_handles_invalid_flag_gracefully(self):
        """Test raw response handles invalid flag data gracefully."""
        from backend.api.schemas.llm_response import LLMRawResponse

        # Flag with invalid severity
        raw = LLMRawResponse(
            risk_score=50,
            risk_level="medium",
            flags=[{"type": "test", "description": "Test", "severity": "low"}],
        )

        validated = raw.to_validated_response()
        # Invalid flags should be filtered out
        assert validated.flags == []

    def test_raw_response_handles_missing_advanced_fields(self):
        """Test raw response handles missing advanced fields."""
        from backend.api.schemas.llm_response import LLMRawResponse

        raw = LLMRawResponse(
            risk_score=50,
            risk_level="medium",
            # No advanced fields provided
        )

        validated = raw.to_validated_response()

        assert validated.entities == []
        assert validated.flags == []
        assert validated.recommended_action is None
        assert validated.confidence_factors is None
