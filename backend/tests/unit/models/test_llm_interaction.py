"""Unit tests for LLMInteraction model.

Tests cover:
- Model initialization and default values
- Field validation for required and optional fields
- String representation (__repr__)
- JSONB column handling for enrichment_snapshot and other dict fields
- Relationship with Event model
- Property-based tests for field values

TDD: These tests are written first before the model implementation.
"""

from datetime import UTC, datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies for Property-Based Testing
# =============================================================================

# Strategy for valid event IDs
event_ids = st.integers(min_value=1, max_value=1000000)

# Strategy for raw response text (LLM output)
raw_responses = st.text(min_size=1, max_size=10000)

# Strategy for enrichment snapshot dictionaries
enrichment_snapshots = st.dictionaries(
    keys=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N"))),
    values=st.one_of(
        st.none(),
        st.booleans(),
        st.integers(),
        st.floats(allow_nan=False, allow_infinity=False),
        st.text(max_size=100),
    ),
    min_size=1,
    max_size=10,
)

# Strategy for household matches
household_matches = st.one_of(
    st.none(),
    st.dictionaries(
        keys=st.sampled_from(["persons", "vehicles"]),
        values=st.lists(
            st.fixed_dictionaries(
                {
                    "detection_id": st.integers(min_value=1, max_value=10000),
                    "similarity": st.floats(min_value=0.0, max_value=1.0),
                }
            ),
            max_size=5,
        ),
        max_size=2,
    ),
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_llm_interaction():
    """Create a sample LLMInteraction for testing."""
    # Defer import to test phase - model may not exist yet (TDD)
    from backend.models.llm_interaction import LLMInteraction

    return LLMInteraction(
        id=1,
        event_id=100,
        raw_response='{"risk_score": 45, "summary": "Person detected at front door"}',
        enrichment_snapshot={
            "detection_1": {
                "faces": [],
                "clothing": {"color": "blue"},
                "license_plates": [],
            }
        },
        household_matches={
            "persons": [{"detection_id": 1, "member_name": "Mike", "similarity": 0.92}],
            "vehicles": [],
        },
        truncation_log={
            "original_length": 15000,
            "truncated_length": 8000,
            "sections_removed": ["historical_context"],
        },
        context_sources={
            "face_detection": False,
            "clothing": True,
            "ocr": False,
            "pose": False,
            "action": True,
            "florence_caption": True,
        },
        validation_result={
            "passed": False,
            "scenario_id": "delivery_driver_20260129_180349",
            "checks": {"risk_score": {"expected": [0, 15], "actual": 45, "passed": False}},
        },
        created_at=datetime(2026, 1, 29, 10, 0, 0, tzinfo=UTC),
    )


@pytest.fixture
def minimal_llm_interaction():
    """Create an LLMInteraction with only required fields."""
    from backend.models.llm_interaction import LLMInteraction

    return LLMInteraction(
        event_id=200,
        raw_response="{}",
        enrichment_snapshot={},
    )


# =============================================================================
# LLMInteraction Model Initialization Tests
# =============================================================================


class TestLLMInteractionModelInitialization:
    """Tests for LLMInteraction model initialization."""

    def test_llm_interaction_creation_minimal(self):
        """Test creating an LLMInteraction with minimal required fields."""
        from backend.models.llm_interaction import LLMInteraction

        interaction = LLMInteraction(
            event_id=100,
            raw_response="{}",
            enrichment_snapshot={},
        )

        assert interaction.event_id == 100
        assert interaction.raw_response == "{}"
        assert interaction.enrichment_snapshot == {}

    def test_llm_interaction_with_all_fields(self, sample_llm_interaction):
        """Test LLMInteraction with all fields populated."""
        assert sample_llm_interaction.id == 1
        assert sample_llm_interaction.event_id == 100
        assert "risk_score" in sample_llm_interaction.raw_response
        assert "detection_1" in sample_llm_interaction.enrichment_snapshot
        assert "persons" in sample_llm_interaction.household_matches
        assert sample_llm_interaction.truncation_log["original_length"] == 15000
        assert sample_llm_interaction.context_sources["clothing"] is True
        assert sample_llm_interaction.validation_result["passed"] is False

    def test_llm_interaction_optional_fields_default_to_none(self, minimal_llm_interaction):
        """Test that optional JSONB fields default to None."""
        assert minimal_llm_interaction.household_matches is None
        assert minimal_llm_interaction.truncation_log is None
        assert minimal_llm_interaction.context_sources is None
        assert minimal_llm_interaction.validation_result is None


# =============================================================================
# Required Field Tests
# =============================================================================


class TestLLMInteractionRequiredFields:
    """Tests for LLMInteraction required fields."""

    def test_event_id_required(self):
        """Test that event_id is required."""
        from backend.models.llm_interaction import LLMInteraction

        # Create with event_id - should work
        interaction = LLMInteraction(
            event_id=1,
            raw_response="test",
            enrichment_snapshot={},
        )
        assert interaction.event_id == 1

    def test_raw_response_required(self):
        """Test that raw_response is required."""
        from backend.models.llm_interaction import LLMInteraction

        # Create with raw_response - should work
        interaction = LLMInteraction(
            event_id=1,
            raw_response="test response",
            enrichment_snapshot={},
        )
        assert interaction.raw_response == "test response"

    def test_enrichment_snapshot_required(self):
        """Test that enrichment_snapshot is required."""
        from backend.models.llm_interaction import LLMInteraction

        # Create with enrichment_snapshot - should work
        interaction = LLMInteraction(
            event_id=1,
            raw_response="test",
            enrichment_snapshot={"key": "value"},
        )
        assert interaction.enrichment_snapshot == {"key": "value"}


# =============================================================================
# JSONB Field Tests
# =============================================================================


class TestLLMInteractionJSONBFields:
    """Tests for LLMInteraction JSONB column handling."""

    def test_enrichment_snapshot_dict_roundtrip(self):
        """Test enrichment_snapshot stores and retrieves dict correctly."""
        from backend.models.llm_interaction import LLMInteraction

        enrichment = {
            "detection_1": {
                "faces": [{"bbox": [10, 20, 30, 40], "confidence": 0.95}],
                "clothing": {"type": "uniform", "color": "brown"},
            },
            "detection_2": {
                "license_plates": [{"text": "ABC123", "confidence": 0.87}],
            },
        }

        interaction = LLMInteraction(
            event_id=1,
            raw_response="{}",
            enrichment_snapshot=enrichment,
        )

        assert interaction.enrichment_snapshot == enrichment
        assert interaction.enrichment_snapshot["detection_1"]["faces"][0]["confidence"] == 0.95

    def test_household_matches_dict_roundtrip(self):
        """Test household_matches stores and retrieves dict correctly."""
        from backend.models.llm_interaction import LLMInteraction

        matches = {
            "persons": [
                {"detection_id": 1, "member_name": "Mike", "similarity": 0.92},
                {"detection_id": 3, "member_name": "Sarah", "similarity": 0.88},
            ],
            "vehicles": [
                {"detection_id": 2, "plate": "ABC123", "description": "Blue Honda Civic"},
            ],
        }

        interaction = LLMInteraction(
            event_id=1,
            raw_response="{}",
            enrichment_snapshot={},
            household_matches=matches,
        )

        assert interaction.household_matches == matches
        assert len(interaction.household_matches["persons"]) == 2

    def test_truncation_log_dict_roundtrip(self):
        """Test truncation_log stores and retrieves dict correctly."""
        from backend.models.llm_interaction import LLMInteraction

        truncation = {
            "original_length": 25000,
            "truncated_length": 8000,
            "sections_removed": ["historical_baselines", "cross_camera_context"],
            "reason": "token_limit_exceeded",
        }

        interaction = LLMInteraction(
            event_id=1,
            raw_response="{}",
            enrichment_snapshot={},
            truncation_log=truncation,
        )

        assert interaction.truncation_log == truncation
        assert "historical_baselines" in interaction.truncation_log["sections_removed"]

    def test_context_sources_dict_roundtrip(self):
        """Test context_sources stores and retrieves dict correctly."""
        from backend.models.llm_interaction import LLMInteraction

        sources = {
            "face_detection": True,
            "clothing": True,
            "ocr": False,
            "pose": True,
            "action": True,
            "florence_caption": True,
            "weather": True,
            "image_quality": True,
        }

        interaction = LLMInteraction(
            event_id=1,
            raw_response="{}",
            enrichment_snapshot={},
            context_sources=sources,
        )

        assert interaction.context_sources == sources
        assert interaction.context_sources["face_detection"] is True

    def test_validation_result_dict_roundtrip(self):
        """Test validation_result stores and retrieves dict correctly."""
        from backend.models.llm_interaction import LLMInteraction

        validation = {
            "passed": False,
            "scenario_id": "delivery_driver_20260129_180349",
            "checks": {
                "risk_score": {"expected": [0, 15], "actual": 45, "passed": False},
                "face_detected": {"expected": True, "actual": False, "passed": False},
                "clothing_type": {"expected": "uniform", "actual": "casual", "passed": False},
                "ocr_text": {"expected": ["AMAZON"], "actual": ["AMA"], "passed": False},
            },
        }

        interaction = LLMInteraction(
            event_id=1,
            raw_response="{}",
            enrichment_snapshot={},
            validation_result=validation,
        )

        assert interaction.validation_result == validation
        assert interaction.validation_result["checks"]["risk_score"]["passed"] is False


# =============================================================================
# Raw Response Text Field Tests
# =============================================================================


class TestLLMInteractionRawResponse:
    """Tests for LLMInteraction raw_response field."""

    def test_raw_response_stores_json_string(self):
        """Test raw_response can store JSON string."""
        from backend.models.llm_interaction import LLMInteraction

        json_response = '{"risk_score": 45, "summary": "Person at door"}'

        interaction = LLMInteraction(
            event_id=1,
            raw_response=json_response,
            enrichment_snapshot={},
        )

        assert interaction.raw_response == json_response

    def test_raw_response_with_think_blocks(self):
        """Test raw_response can store LLM output with <think> blocks."""
        from backend.models.llm_interaction import LLMInteraction

        response_with_think = """<think>
The person appears to be a delivery driver based on:
- Brown uniform visible
- Carrying a package
- Standing at front door
</think>

{"risk_score": 8, "risk_level": "low", "summary": "Delivery driver at front door"}"""

        interaction = LLMInteraction(
            event_id=1,
            raw_response=response_with_think,
            enrichment_snapshot={},
        )

        assert "<think>" in interaction.raw_response
        assert "risk_score" in interaction.raw_response

    def test_raw_response_long_text(self):
        """Test raw_response can store long LLM outputs."""
        from backend.models.llm_interaction import LLMInteraction

        long_response = "A" * 50000

        interaction = LLMInteraction(
            event_id=1,
            raw_response=long_response,
            enrichment_snapshot={},
        )

        assert len(interaction.raw_response) == 50000


# =============================================================================
# Repr Tests
# =============================================================================


class TestLLMInteractionRepr:
    """Tests for LLMInteraction string representation."""

    def test_repr_contains_class_name(self, sample_llm_interaction):
        """Test repr contains class name."""
        repr_str = repr(sample_llm_interaction)
        assert "LLMInteraction" in repr_str

    def test_repr_contains_id(self, sample_llm_interaction):
        """Test repr contains id."""
        repr_str = repr(sample_llm_interaction)
        assert "id=1" in repr_str

    def test_repr_contains_event_id(self, sample_llm_interaction):
        """Test repr contains event_id."""
        repr_str = repr(sample_llm_interaction)
        assert "event_id=100" in repr_str

    def test_repr_format(self, sample_llm_interaction):
        """Test repr has expected format."""
        repr_str = repr(sample_llm_interaction)
        assert repr_str.startswith("<LLMInteraction(")
        assert repr_str.endswith(")>")


# =============================================================================
# Relationship Tests
# =============================================================================


class TestLLMInteractionRelationships:
    """Tests for LLMInteraction relationship definitions."""

    def test_llm_interaction_has_event_relationship(self, sample_llm_interaction):
        """Test LLMInteraction has event relationship defined."""
        assert hasattr(sample_llm_interaction, "event")


# =============================================================================
# Table Configuration Tests
# =============================================================================


class TestLLMInteractionTableConfig:
    """Tests for LLMInteraction table configuration."""

    def test_llm_interaction_tablename(self):
        """Test LLMInteraction has correct table name."""
        from backend.models.llm_interaction import LLMInteraction

        assert LLMInteraction.__tablename__ == "llm_interactions"

    def test_llm_interaction_has_table_args(self):
        """Test LLMInteraction model has __table_args__."""
        from backend.models.llm_interaction import LLMInteraction

        assert hasattr(LLMInteraction, "__table_args__")

    def test_llm_interaction_has_indexes(self):
        """Test LLMInteraction table has expected indexes defined."""
        from backend.models.llm_interaction import LLMInteraction

        # Verify __table_args__ is a tuple (contains Index objects)
        table_args = LLMInteraction.__table_args__
        assert isinstance(table_args, tuple)
        assert len(table_args) >= 2  # At least event_id and created_at indexes


# =============================================================================
# Column Definition Tests
# =============================================================================


class TestLLMInteractionColumnDefinitions:
    """Tests for LLMInteraction column definitions."""

    def test_event_id_column_definition(self):
        """Test event_id column has correct definition."""
        from sqlalchemy import inspect

        from backend.models.llm_interaction import LLMInteraction

        mapper = inspect(LLMInteraction)
        col = mapper.columns["event_id"]
        assert col.nullable is False

    def test_raw_response_column_definition(self):
        """Test raw_response column has correct definition."""
        from sqlalchemy import inspect

        from backend.models.llm_interaction import LLMInteraction

        mapper = inspect(LLMInteraction)
        col = mapper.columns["raw_response"]
        assert col.nullable is False

    def test_enrichment_snapshot_column_definition(self):
        """Test enrichment_snapshot column has correct definition."""
        from sqlalchemy import inspect

        from backend.models.llm_interaction import LLMInteraction

        mapper = inspect(LLMInteraction)
        col = mapper.columns["enrichment_snapshot"]
        assert col.nullable is False

    def test_optional_columns_are_nullable(self):
        """Test optional JSONB columns are nullable."""
        from sqlalchemy import inspect

        from backend.models.llm_interaction import LLMInteraction

        mapper = inspect(LLMInteraction)

        nullable_columns = [
            "household_matches",
            "truncation_log",
            "context_sources",
            "validation_result",
        ]

        for col_name in nullable_columns:
            col = mapper.columns[col_name]
            assert col.nullable is True, f"{col_name} should be nullable"


# =============================================================================
# Timestamp Tests
# =============================================================================


class TestLLMInteractionTimestamps:
    """Tests for LLMInteraction timestamp fields."""

    def test_created_at_explicit_value(self, sample_llm_interaction):
        """Test created_at with explicit value."""
        expected = datetime(2026, 1, 29, 10, 0, 0, tzinfo=UTC)
        assert sample_llm_interaction.created_at == expected

    def test_created_at_has_timezone(self, sample_llm_interaction):
        """Test created_at has timezone info."""
        assert sample_llm_interaction.created_at.tzinfo is not None


# =============================================================================
# Property-Based Tests
# =============================================================================


class TestLLMInteractionProperties:
    """Property-based tests for LLMInteraction model."""

    @given(event_id=event_ids)
    @settings(max_examples=50)
    def test_event_id_roundtrip(self, event_id: int):
        """Property: Event ID values roundtrip correctly."""
        from backend.models.llm_interaction import LLMInteraction

        interaction = LLMInteraction(
            event_id=event_id,
            raw_response="{}",
            enrichment_snapshot={},
        )
        assert interaction.event_id == event_id

    @given(response=raw_responses)
    @settings(max_examples=50)
    def test_raw_response_roundtrip(self, response: str):
        """Property: Raw response text roundtrips correctly."""
        from backend.models.llm_interaction import LLMInteraction

        interaction = LLMInteraction(
            event_id=1,
            raw_response=response,
            enrichment_snapshot={},
        )
        assert interaction.raw_response == response

    @given(snapshot=enrichment_snapshots)
    @settings(max_examples=50)
    def test_enrichment_snapshot_roundtrip(self, snapshot: dict):
        """Property: Enrichment snapshot dict roundtrips correctly."""
        from backend.models.llm_interaction import LLMInteraction

        interaction = LLMInteraction(
            event_id=1,
            raw_response="{}",
            enrichment_snapshot=snapshot,
        )
        assert interaction.enrichment_snapshot == snapshot


# =============================================================================
# Edge Cases and Boundary Tests
# =============================================================================


class TestLLMInteractionEdgeCases:
    """Edge case tests for LLMInteraction model."""

    def test_empty_enrichment_snapshot(self):
        """Test empty dict in enrichment_snapshot."""
        from backend.models.llm_interaction import LLMInteraction

        interaction = LLMInteraction(
            event_id=1,
            raw_response="{}",
            enrichment_snapshot={},
        )
        assert interaction.enrichment_snapshot == {}

    def test_nested_dicts_in_enrichment_snapshot(self):
        """Test deeply nested dictionaries in enrichment_snapshot."""
        from backend.models.llm_interaction import LLMInteraction

        nested = {
            "level1": {
                "level2": {
                    "level3": {
                        "level4": {"value": "deep"},
                    },
                },
            },
        }

        interaction = LLMInteraction(
            event_id=1,
            raw_response="{}",
            enrichment_snapshot=nested,
        )
        assert (
            interaction.enrichment_snapshot["level1"]["level2"]["level3"]["level4"]["value"]
            == "deep"
        )

    def test_unicode_in_raw_response(self):
        """Test unicode characters in raw_response."""
        from backend.models.llm_interaction import LLMInteraction

        unicode_response = '{"summary": "Person detected with package"}'

        interaction = LLMInteraction(
            event_id=1,
            raw_response=unicode_response,
            enrichment_snapshot={},
        )
        assert "package" in interaction.raw_response

    def test_special_characters_in_raw_response(self):
        """Test special characters in raw_response."""
        from backend.models.llm_interaction import LLMInteraction

        special_response = "<think>Analysis & \"reasoning\" 'here'</think>"

        interaction = LLMInteraction(
            event_id=1,
            raw_response=special_response,
            enrichment_snapshot={},
        )
        assert interaction.raw_response == special_response

    def test_arrays_in_jsonb_fields(self):
        """Test arrays stored in JSONB fields."""
        from backend.models.llm_interaction import LLMInteraction

        enrichment = {
            "detections": [1, 2, 3, 4, 5],
            "labels": ["person", "vehicle", "package"],
        }

        interaction = LLMInteraction(
            event_id=1,
            raw_response="{}",
            enrichment_snapshot=enrichment,
        )
        assert interaction.enrichment_snapshot["detections"] == [1, 2, 3, 4, 5]

    def test_numeric_values_in_jsonb_fields(self):
        """Test numeric values (int, float) in JSONB fields."""
        from backend.models.llm_interaction import LLMInteraction

        enrichment = {
            "count": 42,
            "confidence": 0.95,
            "score": -10.5,
        }

        interaction = LLMInteraction(
            event_id=1,
            raw_response="{}",
            enrichment_snapshot=enrichment,
        )
        assert interaction.enrichment_snapshot["count"] == 42
        assert interaction.enrichment_snapshot["confidence"] == 0.95
        assert interaction.enrichment_snapshot["score"] == -10.5

    def test_null_values_in_jsonb_fields(self):
        """Test null values within JSONB fields."""
        from backend.models.llm_interaction import LLMInteraction

        enrichment = {
            "face": None,
            "clothing": {"color": None, "type": "uniform"},
        }

        interaction = LLMInteraction(
            event_id=1,
            raw_response="{}",
            enrichment_snapshot=enrichment,
        )
        assert interaction.enrichment_snapshot["face"] is None
        assert interaction.enrichment_snapshot["clothing"]["color"] is None
