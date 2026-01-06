"""Unit tests for LLM response Pydantic schemas.

These tests cover the LLM response validation schemas including:
- LLMRiskResponse: Risk assessment response from Nemotron
- LLMRawResponse: Raw parsed response before validation
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
            "confidence": 0.95,  # Extra field
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
