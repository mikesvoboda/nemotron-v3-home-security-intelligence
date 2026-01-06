"""Unit tests for EventAudit model.

Tests cover:
- Model initialization and default values
- Field validation and constraints
- String representation (__repr__)
- Boolean model contribution flags
- Score fields and metrics
- Text fields for evaluation and suggestions
- is_fully_evaluated property
- Property-based tests for field values
"""

from datetime import UTC, datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.models.event_audit import EventAudit

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for valid quality scores (1-5 scale)
quality_scores = st.floats(min_value=1.0, max_value=5.0, allow_nan=False, allow_infinity=False)

# Strategy for prompt metrics
prompt_lengths = st.integers(min_value=0, max_value=100000)
token_estimates = st.integers(min_value=0, max_value=50000)
utilization_rates = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

# Strategy for risk scores
risk_scores = st.integers(min_value=0, max_value=100)

# Strategy for consistency diffs (can be negative, positive, or zero)
consistency_diffs = st.integers(min_value=-100, max_value=100)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_event_audit():
    """Create a sample EventAudit for testing."""
    return EventAudit(
        id=1,
        event_id=100,
        audited_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        has_rtdetr=True,
        has_florence=True,
        has_clip=False,
        has_violence=False,
        has_clothing=True,
        has_vehicle=False,
        has_pet=False,
        has_weather=True,
        has_image_quality=True,
        has_zones=True,
        has_baseline=True,
        has_cross_camera=False,
        prompt_length=5000,
        prompt_token_estimate=1250,
        enrichment_utilization=0.75,
        context_usage_score=4.5,
        reasoning_coherence_score=4.0,
        risk_justification_score=4.2,
        consistency_score=4.8,
        overall_quality_score=4.3,
        consistency_risk_score=45,
        consistency_diff=5,
        self_eval_critique="Good analysis but could use more context.",
        self_eval_prompt="Evaluate the following...",
        self_eval_response="The analysis was comprehensive...",
        missing_context='["weather_data", "historical_patterns"]',
        confusing_sections='["risk_calculation"]',
        unused_data='["pet_detection"]',
        format_suggestions='["use_bullet_points"]',
        model_gaps='["action_recognition"]',
    )


@pytest.fixture
def minimal_event_audit():
    """Create an EventAudit with only required fields."""
    return EventAudit(
        event_id=200,
    )


@pytest.fixture
def unevaluated_audit():
    """Create an EventAudit without self-evaluation scores."""
    return EventAudit(
        id=2,
        event_id=201,
        has_rtdetr=True,
        has_florence=False,
        prompt_length=3000,
        prompt_token_estimate=750,
        enrichment_utilization=0.5,
    )


@pytest.fixture
def fully_evaluated_audit():
    """Create an EventAudit with complete self-evaluation."""
    return EventAudit(
        id=3,
        event_id=202,
        context_usage_score=4.0,
        reasoning_coherence_score=4.5,
        risk_justification_score=4.0,
        consistency_score=4.0,
        overall_quality_score=4.2,
    )


# =============================================================================
# EventAudit Model Initialization Tests
# =============================================================================


class TestEventAuditModelInitialization:
    """Tests for EventAudit model initialization."""

    def test_event_audit_creation_minimal(self):
        """Test creating an EventAudit with minimal required fields."""
        audit = EventAudit(event_id=100)

        assert audit.event_id == 100

    def test_event_audit_with_all_fields(self, sample_event_audit):
        """Test EventAudit with all fields populated."""
        assert sample_event_audit.id == 1
        assert sample_event_audit.event_id == 100
        assert sample_event_audit.audited_at == datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)
        assert sample_event_audit.has_rtdetr is True
        assert sample_event_audit.has_florence is True
        assert sample_event_audit.has_clip is False
        assert sample_event_audit.prompt_length == 5000
        assert sample_event_audit.prompt_token_estimate == 1250
        assert sample_event_audit.enrichment_utilization == 0.75
        assert sample_event_audit.overall_quality_score == 4.3

    def test_event_audit_boolean_fields_default_to_false_column_definition(self):
        """Test that boolean fields have False as default in column definition.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        This test verifies the column defaults are correctly defined.
        """
        from sqlalchemy import inspect

        mapper = inspect(EventAudit)

        boolean_fields = [
            "has_rtdetr",
            "has_florence",
            "has_clip",
            "has_violence",
            "has_clothing",
            "has_vehicle",
            "has_pet",
            "has_weather",
            "has_image_quality",
            "has_zones",
            "has_baseline",
            "has_cross_camera",
        ]

        for field_name in boolean_fields:
            col = mapper.columns[field_name]
            assert col.default is not None, f"{field_name} should have a default"
            assert col.default.arg is False, f"{field_name} default should be False"

    def test_event_audit_prompt_metrics_default_column_definition(self):
        """Test that prompt metric fields have correct defaults in column definition."""
        from sqlalchemy import inspect

        mapper = inspect(EventAudit)

        # prompt_length default is 0
        prompt_length_col = mapper.columns["prompt_length"]
        assert prompt_length_col.default is not None
        assert prompt_length_col.default.arg == 0

        # prompt_token_estimate default is 0
        token_col = mapper.columns["prompt_token_estimate"]
        assert token_col.default is not None
        assert token_col.default.arg == 0

        # enrichment_utilization default is 0.0
        utilization_col = mapper.columns["enrichment_utilization"]
        assert utilization_col.default is not None
        assert utilization_col.default.arg == 0.0

    def test_event_audit_optional_scores_default_to_none(self, minimal_event_audit):
        """Test that optional score fields default to None."""
        assert minimal_event_audit.context_usage_score is None
        assert minimal_event_audit.reasoning_coherence_score is None
        assert minimal_event_audit.risk_justification_score is None
        assert minimal_event_audit.consistency_score is None
        assert minimal_event_audit.overall_quality_score is None

    def test_event_audit_optional_text_fields_default_to_none(self, minimal_event_audit):
        """Test that optional text fields default to None."""
        assert minimal_event_audit.self_eval_critique is None
        assert minimal_event_audit.self_eval_prompt is None
        assert minimal_event_audit.self_eval_response is None
        assert minimal_event_audit.missing_context is None
        assert minimal_event_audit.confusing_sections is None
        assert minimal_event_audit.unused_data is None
        assert minimal_event_audit.format_suggestions is None
        assert minimal_event_audit.model_gaps is None


# =============================================================================
# Model Contribution Flag Tests
# =============================================================================


class TestEventAuditContributionFlags:
    """Tests for EventAudit model contribution boolean flags."""

    def test_rtdetr_flag_true(self):
        """Test has_rtdetr flag set to True."""
        audit = EventAudit(event_id=1, has_rtdetr=True)
        assert audit.has_rtdetr is True

    def test_rtdetr_flag_false(self):
        """Test has_rtdetr flag set to False."""
        audit = EventAudit(event_id=1, has_rtdetr=False)
        assert audit.has_rtdetr is False

    def test_florence_flag(self):
        """Test has_florence flag."""
        audit = EventAudit(event_id=1, has_florence=True)
        assert audit.has_florence is True

    def test_clip_flag(self):
        """Test has_clip flag."""
        audit = EventAudit(event_id=1, has_clip=True)
        assert audit.has_clip is True

    def test_violence_flag(self):
        """Test has_violence flag."""
        audit = EventAudit(event_id=1, has_violence=True)
        assert audit.has_violence is True

    def test_clothing_flag(self):
        """Test has_clothing flag."""
        audit = EventAudit(event_id=1, has_clothing=True)
        assert audit.has_clothing is True

    def test_vehicle_flag(self):
        """Test has_vehicle flag."""
        audit = EventAudit(event_id=1, has_vehicle=True)
        assert audit.has_vehicle is True

    def test_pet_flag(self):
        """Test has_pet flag."""
        audit = EventAudit(event_id=1, has_pet=True)
        assert audit.has_pet is True

    def test_weather_flag(self):
        """Test has_weather flag."""
        audit = EventAudit(event_id=1, has_weather=True)
        assert audit.has_weather is True

    def test_image_quality_flag(self):
        """Test has_image_quality flag."""
        audit = EventAudit(event_id=1, has_image_quality=True)
        assert audit.has_image_quality is True

    def test_zones_flag(self):
        """Test has_zones flag."""
        audit = EventAudit(event_id=1, has_zones=True)
        assert audit.has_zones is True

    def test_baseline_flag(self):
        """Test has_baseline flag."""
        audit = EventAudit(event_id=1, has_baseline=True)
        assert audit.has_baseline is True

    def test_cross_camera_flag(self):
        """Test has_cross_camera flag."""
        audit = EventAudit(event_id=1, has_cross_camera=True)
        assert audit.has_cross_camera is True

    def test_multiple_flags_combination(self, sample_event_audit):
        """Test multiple contribution flags set together."""
        # True flags
        assert sample_event_audit.has_rtdetr is True
        assert sample_event_audit.has_florence is True
        assert sample_event_audit.has_clothing is True
        assert sample_event_audit.has_weather is True
        assert sample_event_audit.has_image_quality is True
        assert sample_event_audit.has_zones is True
        assert sample_event_audit.has_baseline is True

        # False flags
        assert sample_event_audit.has_clip is False
        assert sample_event_audit.has_violence is False
        assert sample_event_audit.has_vehicle is False
        assert sample_event_audit.has_pet is False
        assert sample_event_audit.has_cross_camera is False


# =============================================================================
# Prompt Metrics Tests
# =============================================================================


class TestEventAuditPromptMetrics:
    """Tests for EventAudit prompt metrics fields."""

    def test_prompt_length(self, sample_event_audit):
        """Test prompt_length field."""
        assert sample_event_audit.prompt_length == 5000

    def test_prompt_length_zero(self):
        """Test prompt_length can be zero."""
        audit = EventAudit(event_id=1, prompt_length=0)
        assert audit.prompt_length == 0

    def test_prompt_length_large(self):
        """Test prompt_length can be large."""
        audit = EventAudit(event_id=1, prompt_length=100000)
        assert audit.prompt_length == 100000

    def test_prompt_token_estimate(self, sample_event_audit):
        """Test prompt_token_estimate field."""
        assert sample_event_audit.prompt_token_estimate == 1250

    def test_prompt_token_estimate_zero(self):
        """Test prompt_token_estimate can be zero."""
        audit = EventAudit(event_id=1, prompt_token_estimate=0)
        assert audit.prompt_token_estimate == 0

    def test_enrichment_utilization(self, sample_event_audit):
        """Test enrichment_utilization field."""
        assert sample_event_audit.enrichment_utilization == 0.75

    def test_enrichment_utilization_zero(self):
        """Test enrichment_utilization can be zero."""
        audit = EventAudit(event_id=1, enrichment_utilization=0.0)
        assert audit.enrichment_utilization == 0.0

    def test_enrichment_utilization_one(self):
        """Test enrichment_utilization can be one (100%)."""
        audit = EventAudit(event_id=1, enrichment_utilization=1.0)
        assert audit.enrichment_utilization == 1.0


# =============================================================================
# Self-Evaluation Score Tests
# =============================================================================


class TestEventAuditSelfEvaluationScores:
    """Tests for EventAudit self-evaluation score fields."""

    def test_context_usage_score(self, sample_event_audit):
        """Test context_usage_score field."""
        assert sample_event_audit.context_usage_score == 4.5

    def test_context_usage_score_min(self):
        """Test context_usage_score minimum (1.0)."""
        audit = EventAudit(event_id=1, context_usage_score=1.0)
        assert audit.context_usage_score == 1.0

    def test_context_usage_score_max(self):
        """Test context_usage_score maximum (5.0)."""
        audit = EventAudit(event_id=1, context_usage_score=5.0)
        assert audit.context_usage_score == 5.0

    def test_reasoning_coherence_score(self, sample_event_audit):
        """Test reasoning_coherence_score field."""
        assert sample_event_audit.reasoning_coherence_score == 4.0

    def test_risk_justification_score(self, sample_event_audit):
        """Test risk_justification_score field."""
        assert sample_event_audit.risk_justification_score == 4.2

    def test_consistency_score(self, sample_event_audit):
        """Test consistency_score field."""
        assert sample_event_audit.consistency_score == 4.8

    def test_overall_quality_score(self, sample_event_audit):
        """Test overall_quality_score field."""
        assert sample_event_audit.overall_quality_score == 4.3

    def test_all_scores_none_when_not_evaluated(self, unevaluated_audit):
        """Test all score fields are None for unevaluated audit."""
        assert unevaluated_audit.context_usage_score is None
        assert unevaluated_audit.reasoning_coherence_score is None
        assert unevaluated_audit.risk_justification_score is None
        assert unevaluated_audit.consistency_score is None
        assert unevaluated_audit.overall_quality_score is None


# =============================================================================
# Consistency Check Fields Tests
# =============================================================================


class TestEventAuditConsistencyCheck:
    """Tests for EventAudit consistency check fields."""

    def test_consistency_risk_score(self, sample_event_audit):
        """Test consistency_risk_score field."""
        assert sample_event_audit.consistency_risk_score == 45

    def test_consistency_risk_score_none(self, minimal_event_audit):
        """Test consistency_risk_score is None by default."""
        assert minimal_event_audit.consistency_risk_score is None

    def test_consistency_risk_score_boundary_zero(self):
        """Test consistency_risk_score can be zero."""
        audit = EventAudit(event_id=1, consistency_risk_score=0)
        assert audit.consistency_risk_score == 0

    def test_consistency_risk_score_boundary_hundred(self):
        """Test consistency_risk_score can be 100."""
        audit = EventAudit(event_id=1, consistency_risk_score=100)
        assert audit.consistency_risk_score == 100

    def test_consistency_diff(self, sample_event_audit):
        """Test consistency_diff field."""
        assert sample_event_audit.consistency_diff == 5

    def test_consistency_diff_none(self, minimal_event_audit):
        """Test consistency_diff is None by default."""
        assert minimal_event_audit.consistency_diff is None

    def test_consistency_diff_negative(self):
        """Test consistency_diff can be negative."""
        audit = EventAudit(event_id=1, consistency_diff=-10)
        assert audit.consistency_diff == -10

    def test_consistency_diff_positive(self):
        """Test consistency_diff can be positive."""
        audit = EventAudit(event_id=1, consistency_diff=25)
        assert audit.consistency_diff == 25

    def test_consistency_diff_zero(self):
        """Test consistency_diff can be zero (perfect match)."""
        audit = EventAudit(event_id=1, consistency_diff=0)
        assert audit.consistency_diff == 0


# =============================================================================
# Self-Evaluation Text Fields Tests
# =============================================================================


class TestEventAuditSelfEvaluationText:
    """Tests for EventAudit self-evaluation text fields."""

    def test_self_eval_critique(self, sample_event_audit):
        """Test self_eval_critique field."""
        assert sample_event_audit.self_eval_critique == "Good analysis but could use more context."

    def test_self_eval_critique_none(self, minimal_event_audit):
        """Test self_eval_critique is None by default."""
        assert minimal_event_audit.self_eval_critique is None

    def test_self_eval_prompt(self, sample_event_audit):
        """Test self_eval_prompt field."""
        assert sample_event_audit.self_eval_prompt == "Evaluate the following..."

    def test_self_eval_response(self, sample_event_audit):
        """Test self_eval_response field."""
        assert sample_event_audit.self_eval_response == "The analysis was comprehensive..."

    def test_long_critique_text(self):
        """Test self_eval_critique can hold long text."""
        long_text = "A" * 10000
        audit = EventAudit(event_id=1, self_eval_critique=long_text)
        assert audit.self_eval_critique == long_text
        assert len(audit.self_eval_critique) == 10000


# =============================================================================
# Prompt Improvement Suggestions Tests
# =============================================================================


class TestEventAuditPromptImprovementSuggestions:
    """Tests for EventAudit prompt improvement suggestion fields."""

    def test_missing_context(self, sample_event_audit):
        """Test missing_context field (JSON array as text)."""
        assert sample_event_audit.missing_context == '["weather_data", "historical_patterns"]'

    def test_missing_context_none(self, minimal_event_audit):
        """Test missing_context is None by default."""
        assert minimal_event_audit.missing_context is None

    def test_confusing_sections(self, sample_event_audit):
        """Test confusing_sections field."""
        assert sample_event_audit.confusing_sections == '["risk_calculation"]'

    def test_unused_data(self, sample_event_audit):
        """Test unused_data field."""
        assert sample_event_audit.unused_data == '["pet_detection"]'

    def test_format_suggestions(self, sample_event_audit):
        """Test format_suggestions field."""
        assert sample_event_audit.format_suggestions == '["use_bullet_points"]'

    def test_model_gaps(self, sample_event_audit):
        """Test model_gaps field."""
        assert sample_event_audit.model_gaps == '["action_recognition"]'

    def test_json_array_parsing(self):
        """Test that JSON arrays can be stored and parsed back."""
        import json

        suggestions = ["suggestion1", "suggestion2", "suggestion3"]
        json_str = json.dumps(suggestions)

        audit = EventAudit(event_id=1, missing_context=json_str)

        parsed = json.loads(audit.missing_context)
        assert parsed == suggestions


# =============================================================================
# is_fully_evaluated Property Tests
# =============================================================================


class TestEventAuditIsFullyEvaluatedProperty:
    """Tests for EventAudit.is_fully_evaluated property."""

    def test_is_fully_evaluated_true(self, fully_evaluated_audit):
        """Test is_fully_evaluated returns True when overall_quality_score is set."""
        assert fully_evaluated_audit.is_fully_evaluated is True

    def test_is_fully_evaluated_false_no_score(self, unevaluated_audit):
        """Test is_fully_evaluated returns False when overall_quality_score is None."""
        assert unevaluated_audit.is_fully_evaluated is False

    def test_is_fully_evaluated_false_minimal(self, minimal_event_audit):
        """Test is_fully_evaluated returns False for minimal audit."""
        assert minimal_event_audit.is_fully_evaluated is False

    def test_is_fully_evaluated_with_partial_scores(self):
        """Test is_fully_evaluated with partial scores but no overall score."""
        audit = EventAudit(
            event_id=1,
            context_usage_score=4.0,
            reasoning_coherence_score=4.5,
            # No overall_quality_score
        )
        assert audit.is_fully_evaluated is False

    def test_is_fully_evaluated_with_only_overall_score(self):
        """Test is_fully_evaluated when only overall_quality_score is set."""
        audit = EventAudit(event_id=1, overall_quality_score=4.0)
        assert audit.is_fully_evaluated is True


# =============================================================================
# EventAudit Repr Tests
# =============================================================================


class TestEventAuditRepr:
    """Tests for EventAudit string representation."""

    def test_repr_contains_class_name(self, sample_event_audit):
        """Test repr contains class name."""
        repr_str = repr(sample_event_audit)
        assert "EventAudit" in repr_str

    def test_repr_contains_id(self, sample_event_audit):
        """Test repr contains id."""
        repr_str = repr(sample_event_audit)
        assert "id=1" in repr_str

    def test_repr_contains_event_id(self, sample_event_audit):
        """Test repr contains event_id."""
        repr_str = repr(sample_event_audit)
        assert "event_id=100" in repr_str

    def test_repr_contains_overall_score(self, sample_event_audit):
        """Test repr contains overall_quality_score."""
        repr_str = repr(sample_event_audit)
        assert "overall_score=4.3" in repr_str

    def test_repr_with_none_score(self, unevaluated_audit):
        """Test repr with None overall_quality_score."""
        repr_str = repr(unevaluated_audit)
        assert "overall_score=None" in repr_str

    def test_repr_format(self, sample_event_audit):
        """Test repr has expected format."""
        repr_str = repr(sample_event_audit)
        assert repr_str.startswith("<EventAudit(")
        assert repr_str.endswith(")>")


# =============================================================================
# EventAudit Relationship Tests
# =============================================================================


class TestEventAuditRelationships:
    """Tests for EventAudit relationship definitions."""

    def test_event_audit_has_event_relationship(self, sample_event_audit):
        """Test EventAudit has event relationship defined."""
        assert hasattr(sample_event_audit, "event")


# =============================================================================
# EventAudit Table Args Tests
# =============================================================================


class TestEventAuditTableArgs:
    """Tests for EventAudit table arguments (indexes)."""

    def test_event_audit_has_table_args(self):
        """Test EventAudit model has __table_args__."""
        assert hasattr(EventAudit, "__table_args__")

    def test_event_audit_tablename(self):
        """Test EventAudit has correct table name."""
        assert EventAudit.__tablename__ == "event_audits"

    def test_event_audit_has_indexes(self):
        """Test EventAudit table has expected indexes defined."""
        # Verify __table_args__ is a tuple (contains Index objects)
        table_args = EventAudit.__table_args__
        assert isinstance(table_args, tuple)
        assert len(table_args) >= 3  # At least 3 indexes defined


# =============================================================================
# EventAudit Timestamp Tests
# =============================================================================


class TestEventAuditTimestamps:
    """Tests for EventAudit timestamp fields."""

    def test_audited_at_required(self, sample_event_audit):
        """Test audited_at is set."""
        assert sample_event_audit.audited_at is not None

    def test_audited_at_with_timezone(self, sample_event_audit):
        """Test audited_at has timezone info."""
        assert sample_event_audit.audited_at.tzinfo is not None

    def test_audited_at_explicit_value(self, sample_event_audit):
        """Test audited_at with explicit value."""
        expected = datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)
        assert sample_event_audit.audited_at == expected


# =============================================================================
# Property-based Tests
# =============================================================================


class TestEventAuditProperties:
    """Property-based tests for EventAudit model."""

    @given(score=quality_scores)
    @settings(max_examples=50)
    def test_quality_score_roundtrip(self, score: float):
        """Property: Quality score values roundtrip correctly."""
        audit = EventAudit(event_id=1, overall_quality_score=score)
        assert audit.overall_quality_score == score
        assert audit.is_fully_evaluated is True

    @given(
        context=quality_scores,
        reasoning=quality_scores,
        risk_just=quality_scores,
        consistency=quality_scores,
        overall=quality_scores,
    )
    @settings(max_examples=50)
    def test_all_scores_roundtrip(
        self,
        context: float,
        reasoning: float,
        risk_just: float,
        consistency: float,
        overall: float,
    ):
        """Property: All score fields roundtrip correctly."""
        audit = EventAudit(
            event_id=1,
            context_usage_score=context,
            reasoning_coherence_score=reasoning,
            risk_justification_score=risk_just,
            consistency_score=consistency,
            overall_quality_score=overall,
        )
        assert audit.context_usage_score == context
        assert audit.reasoning_coherence_score == reasoning
        assert audit.risk_justification_score == risk_just
        assert audit.consistency_score == consistency
        assert audit.overall_quality_score == overall

    @given(prompt_length=prompt_lengths, token_estimate=token_estimates)
    @settings(max_examples=50)
    def test_prompt_metrics_roundtrip(self, prompt_length: int, token_estimate: int):
        """Property: Prompt metric values roundtrip correctly."""
        audit = EventAudit(
            event_id=1,
            prompt_length=prompt_length,
            prompt_token_estimate=token_estimate,
        )
        assert audit.prompt_length == prompt_length
        assert audit.prompt_token_estimate == token_estimate

    @given(utilization=utilization_rates)
    @settings(max_examples=50)
    def test_enrichment_utilization_roundtrip(self, utilization: float):
        """Property: Enrichment utilization values roundtrip correctly."""
        audit = EventAudit(event_id=1, enrichment_utilization=utilization)
        assert audit.enrichment_utilization == utilization

    @given(risk_score=risk_scores, diff=consistency_diffs)
    @settings(max_examples=50)
    def test_consistency_check_roundtrip(self, risk_score: int, diff: int):
        """Property: Consistency check values roundtrip correctly."""
        audit = EventAudit(
            event_id=1,
            consistency_risk_score=risk_score,
            consistency_diff=diff,
        )
        assert audit.consistency_risk_score == risk_score
        assert audit.consistency_diff == diff

    @given(
        has_rtdetr=st.booleans(),
        has_florence=st.booleans(),
        has_clip=st.booleans(),
        has_violence=st.booleans(),
        has_clothing=st.booleans(),
        has_vehicle=st.booleans(),
    )
    @settings(max_examples=50)
    def test_boolean_flags_roundtrip(
        self,
        has_rtdetr: bool,
        has_florence: bool,
        has_clip: bool,
        has_violence: bool,
        has_clothing: bool,
        has_vehicle: bool,
    ):
        """Property: Boolean flags roundtrip correctly."""
        audit = EventAudit(
            event_id=1,
            has_rtdetr=has_rtdetr,
            has_florence=has_florence,
            has_clip=has_clip,
            has_violence=has_violence,
            has_clothing=has_clothing,
            has_vehicle=has_vehicle,
        )
        assert audit.has_rtdetr == has_rtdetr
        assert audit.has_florence == has_florence
        assert audit.has_clip == has_clip
        assert audit.has_violence == has_violence
        assert audit.has_clothing == has_clothing
        assert audit.has_vehicle == has_vehicle

    @given(text=st.text(max_size=500))
    @settings(max_examples=50)
    def test_text_fields_roundtrip(self, text: str):
        """Property: Text fields roundtrip correctly."""
        audit = EventAudit(
            event_id=1,
            self_eval_critique=text,
            missing_context=text,
        )
        assert audit.self_eval_critique == text
        assert audit.missing_context == text

    @given(event_id=st.integers(min_value=1, max_value=1000000))
    @settings(max_examples=50)
    def test_event_id_roundtrip(self, event_id: int):
        """Property: Event ID values roundtrip correctly."""
        audit = EventAudit(event_id=event_id)
        assert audit.event_id == event_id


# =============================================================================
# Edge Cases and Boundary Tests
# =============================================================================


class TestEventAuditEdgeCases:
    """Edge case tests for EventAudit model."""

    def test_empty_text_fields(self):
        """Test empty string in text fields."""
        audit = EventAudit(
            event_id=1,
            self_eval_critique="",
            missing_context="",
        )
        assert audit.self_eval_critique == ""
        assert audit.missing_context == ""

    def test_unicode_in_text_fields(self):
        """Test unicode characters in text fields."""
        unicode_text = "Analysis includes: cafe, resume, and more"
        audit = EventAudit(event_id=1, self_eval_critique=unicode_text)
        assert audit.self_eval_critique == unicode_text

    def test_special_characters_in_text(self):
        """Test special characters in text fields."""
        special_text = '<script>alert("xss")</script> & "quotes" \'single\''
        audit = EventAudit(event_id=1, self_eval_critique=special_text)
        assert audit.self_eval_critique == special_text

    def test_newlines_in_text(self):
        """Test newlines in text fields."""
        multiline = "Line 1\nLine 2\nLine 3"
        audit = EventAudit(event_id=1, self_eval_critique=multiline)
        assert audit.self_eval_critique == multiline
        assert "\n" in audit.self_eval_critique

    def test_score_boundary_min(self):
        """Test score at minimum boundary (1.0)."""
        audit = EventAudit(
            event_id=1,
            context_usage_score=1.0,
            reasoning_coherence_score=1.0,
            risk_justification_score=1.0,
            consistency_score=1.0,
            overall_quality_score=1.0,
        )
        assert audit.context_usage_score == 1.0
        assert audit.is_fully_evaluated is True

    def test_score_boundary_max(self):
        """Test score at maximum boundary (5.0)."""
        audit = EventAudit(
            event_id=1,
            context_usage_score=5.0,
            reasoning_coherence_score=5.0,
            risk_justification_score=5.0,
            consistency_score=5.0,
            overall_quality_score=5.0,
        )
        assert audit.context_usage_score == 5.0

    def test_fractional_scores(self):
        """Test fractional score values."""
        audit = EventAudit(
            event_id=1,
            context_usage_score=3.7,
            reasoning_coherence_score=4.25,
            overall_quality_score=3.14159,
        )
        assert audit.context_usage_score == 3.7
        assert audit.reasoning_coherence_score == 4.25
        assert abs(audit.overall_quality_score - 3.14159) < 0.0001

    def test_json_complex_array(self):
        """Test complex JSON array in suggestion fields."""
        import json

        complex_data = [
            {"type": "missing", "item": "weather"},
            {"type": "unused", "item": "pet_detection"},
        ]
        json_str = json.dumps(complex_data)

        audit = EventAudit(event_id=1, missing_context=json_str)

        parsed = json.loads(audit.missing_context)
        assert parsed == complex_data
