"""Unit tests for feedback API schemas.

Tests cover:
- FeedbackType enum validation
- ActualThreatLevel enum validation (NEM-3330)
- EventFeedbackCreate validation (required fields, notes, enhanced fields)
- EventFeedbackResponse serialization (including enhanced fields)
- FeedbackStatsResponse aggregation structure

NEM-1908: Create EventFeedback API schemas and routes
NEM-3330: Enhanced feedback fields for Nemotron prompt improvement
"""

import pytest
from pydantic import ValidationError

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# FeedbackType Enum Tests
# =============================================================================


class TestFeedbackType:
    """Tests for FeedbackType enum."""

    def test_feedback_type_false_positive(self):
        """Test FeedbackType.FALSE_POSITIVE value."""
        from backend.api.schemas.feedback import FeedbackType

        assert FeedbackType.FALSE_POSITIVE == "false_positive"
        assert FeedbackType.FALSE_POSITIVE.value == "false_positive"

    def test_feedback_type_missed_threat(self):
        """Test FeedbackType.MISSED_THREAT value."""
        from backend.api.schemas.feedback import FeedbackType

        assert FeedbackType.MISSED_THREAT == "missed_threat"
        assert FeedbackType.MISSED_THREAT.value == "missed_threat"

    def test_feedback_type_severity_wrong(self):
        """Test FeedbackType.SEVERITY_WRONG value."""
        from backend.api.schemas.feedback import FeedbackType

        assert FeedbackType.SEVERITY_WRONG == "severity_wrong"
        assert FeedbackType.SEVERITY_WRONG.value == "severity_wrong"

    def test_feedback_type_accurate(self):
        """Test FeedbackType.ACCURATE value."""
        from backend.api.schemas.feedback import FeedbackType

        assert FeedbackType.ACCURATE == "accurate"
        assert FeedbackType.ACCURATE.value == "accurate"

    def test_feedback_type_is_string_enum(self):
        """Test FeedbackType inherits from str."""
        from backend.api.schemas.feedback import FeedbackType

        # String enum should be directly usable as string
        feedback_type = FeedbackType.FALSE_POSITIVE
        assert isinstance(feedback_type, str)
        assert feedback_type == "false_positive"


# =============================================================================
# ActualThreatLevel Enum Tests (NEM-3330)
# =============================================================================


class TestActualThreatLevel:
    """Tests for ActualThreatLevel enum."""

    def test_actual_threat_level_no_threat(self):
        """Test ActualThreatLevel.NO_THREAT value."""
        from backend.api.schemas.feedback import ActualThreatLevel

        assert ActualThreatLevel.NO_THREAT == "no_threat"
        assert ActualThreatLevel.NO_THREAT.value == "no_threat"

    def test_actual_threat_level_minor_concern(self):
        """Test ActualThreatLevel.MINOR_CONCERN value."""
        from backend.api.schemas.feedback import ActualThreatLevel

        assert ActualThreatLevel.MINOR_CONCERN == "minor_concern"
        assert ActualThreatLevel.MINOR_CONCERN.value == "minor_concern"

    def test_actual_threat_level_genuine_threat(self):
        """Test ActualThreatLevel.GENUINE_THREAT value."""
        from backend.api.schemas.feedback import ActualThreatLevel

        assert ActualThreatLevel.GENUINE_THREAT == "genuine_threat"
        assert ActualThreatLevel.GENUINE_THREAT.value == "genuine_threat"

    def test_actual_threat_level_is_string_enum(self):
        """Test ActualThreatLevel inherits from str."""
        from backend.api.schemas.feedback import ActualThreatLevel

        threat_level = ActualThreatLevel.NO_THREAT
        assert isinstance(threat_level, str)
        assert threat_level == "no_threat"

    def test_actual_threat_level_str_representation(self):
        """Test ActualThreatLevel __str__ method."""
        from backend.api.schemas.feedback import ActualThreatLevel

        assert str(ActualThreatLevel.NO_THREAT) == "no_threat"
        assert str(ActualThreatLevel.MINOR_CONCERN) == "minor_concern"
        assert str(ActualThreatLevel.GENUINE_THREAT) == "genuine_threat"


# =============================================================================
# EventFeedbackCreate Tests
# =============================================================================


class TestEventFeedbackCreate:
    """Tests for EventFeedbackCreate schema."""

    def test_create_with_required_fields_only(self):
        """Test creating feedback with only required fields."""
        from backend.api.schemas.feedback import EventFeedbackCreate, FeedbackType

        feedback = EventFeedbackCreate(
            event_id=123,
            feedback_type=FeedbackType.FALSE_POSITIVE,
        )

        assert feedback.event_id == 123
        assert feedback.feedback_type == FeedbackType.FALSE_POSITIVE
        assert feedback.notes is None

    def test_create_with_notes(self):
        """Test creating feedback with optional notes."""
        from backend.api.schemas.feedback import EventFeedbackCreate, FeedbackType

        feedback = EventFeedbackCreate(
            event_id=456,
            feedback_type=FeedbackType.MISSED_THREAT,
            notes="This was my neighbor's car.",
        )

        assert feedback.event_id == 456
        assert feedback.feedback_type == FeedbackType.MISSED_THREAT
        assert feedback.notes == "This was my neighbor's car."

    def test_create_with_string_feedback_type(self):
        """Test creating feedback with string feedback type."""
        from backend.api.schemas.feedback import EventFeedbackCreate, FeedbackType

        feedback = EventFeedbackCreate(
            event_id=789,
            feedback_type="severity_wrong",
        )

        assert feedback.feedback_type == FeedbackType.SEVERITY_WRONG

    def test_create_with_accurate_feedback_type(self):
        """Test creating feedback with accurate classification."""
        from backend.api.schemas.feedback import EventFeedbackCreate, FeedbackType

        feedback = EventFeedbackCreate(
            event_id=100,
            feedback_type=FeedbackType.ACCURATE,
            notes="Good detection!",
        )

        assert feedback.feedback_type == FeedbackType.ACCURATE

    def test_create_missing_event_id_raises_error(self):
        """Test that missing event_id raises validation error."""
        from backend.api.schemas.feedback import EventFeedbackCreate, FeedbackType

        with pytest.raises(ValidationError) as exc_info:
            EventFeedbackCreate(feedback_type=FeedbackType.FALSE_POSITIVE)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("event_id",) for e in errors)

    def test_create_missing_feedback_type_raises_error(self):
        """Test that missing feedback_type raises validation error."""
        from backend.api.schemas.feedback import EventFeedbackCreate

        with pytest.raises(ValidationError) as exc_info:
            EventFeedbackCreate(event_id=123)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("feedback_type",) for e in errors)

    def test_create_invalid_feedback_type_raises_error(self):
        """Test that invalid feedback_type raises validation error."""
        from backend.api.schemas.feedback import EventFeedbackCreate

        with pytest.raises(ValidationError) as exc_info:
            EventFeedbackCreate(event_id=123, feedback_type="invalid_type")

        errors = exc_info.value.errors()
        assert len(errors) >= 1

    def test_create_event_id_must_be_positive(self):
        """Test that event_id must be positive integer."""
        from backend.api.schemas.feedback import EventFeedbackCreate, FeedbackType

        with pytest.raises(ValidationError) as exc_info:
            EventFeedbackCreate(event_id=-1, feedback_type=FeedbackType.FALSE_POSITIVE)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("event_id",) for e in errors)

    def test_create_event_id_zero_invalid(self):
        """Test that event_id cannot be zero."""
        from backend.api.schemas.feedback import EventFeedbackCreate, FeedbackType

        with pytest.raises(ValidationError) as exc_info:
            EventFeedbackCreate(event_id=0, feedback_type=FeedbackType.FALSE_POSITIVE)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("event_id",) for e in errors)


# =============================================================================
# EventFeedbackCreate Enhanced Fields Tests (NEM-3330)
# =============================================================================


class TestEventFeedbackCreateEnhanced:
    """Tests for EventFeedbackCreate enhanced fields (NEM-3330)."""

    def test_create_with_actual_threat_level(self):
        """Test creating feedback with actual_threat_level."""
        from backend.api.schemas.feedback import (
            ActualThreatLevel,
            EventFeedbackCreate,
            FeedbackType,
        )

        feedback = EventFeedbackCreate(
            event_id=123,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            actual_threat_level=ActualThreatLevel.NO_THREAT,
        )

        assert feedback.actual_threat_level == ActualThreatLevel.NO_THREAT

    def test_create_with_string_actual_threat_level(self):
        """Test creating feedback with string actual_threat_level."""
        from backend.api.schemas.feedback import (
            ActualThreatLevel,
            EventFeedbackCreate,
            FeedbackType,
        )

        feedback = EventFeedbackCreate(
            event_id=123,
            feedback_type=FeedbackType.SEVERITY_WRONG,
            actual_threat_level="minor_concern",
        )

        assert feedback.actual_threat_level == ActualThreatLevel.MINOR_CONCERN

    def test_create_with_suggested_score(self):
        """Test creating feedback with suggested_score."""
        from backend.api.schemas.feedback import EventFeedbackCreate, FeedbackType

        feedback = EventFeedbackCreate(
            event_id=123,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            suggested_score=10,
        )

        assert feedback.suggested_score == 10

    def test_create_suggested_score_valid_range(self):
        """Test suggested_score accepts values 0-100."""
        from backend.api.schemas.feedback import EventFeedbackCreate, FeedbackType

        # Min value
        feedback_min = EventFeedbackCreate(
            event_id=123,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            suggested_score=0,
        )
        assert feedback_min.suggested_score == 0

        # Max value
        feedback_max = EventFeedbackCreate(
            event_id=124,
            feedback_type=FeedbackType.MISSED_THREAT,
            suggested_score=100,
        )
        assert feedback_max.suggested_score == 100

    def test_create_suggested_score_invalid_negative(self):
        """Test suggested_score rejects negative values."""
        from backend.api.schemas.feedback import EventFeedbackCreate, FeedbackType

        with pytest.raises(ValidationError) as exc_info:
            EventFeedbackCreate(
                event_id=123,
                feedback_type=FeedbackType.FALSE_POSITIVE,
                suggested_score=-1,
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("suggested_score",) for e in errors)

    def test_create_suggested_score_invalid_over_100(self):
        """Test suggested_score rejects values over 100."""
        from backend.api.schemas.feedback import EventFeedbackCreate, FeedbackType

        with pytest.raises(ValidationError) as exc_info:
            EventFeedbackCreate(
                event_id=123,
                feedback_type=FeedbackType.FALSE_POSITIVE,
                suggested_score=101,
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("suggested_score",) for e in errors)

    def test_create_with_actual_identity(self):
        """Test creating feedback with actual_identity."""
        from backend.api.schemas.feedback import EventFeedbackCreate, FeedbackType

        feedback = EventFeedbackCreate(
            event_id=123,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            actual_identity="Mike (neighbor)",
        )

        assert feedback.actual_identity == "Mike (neighbor)"

    def test_create_actual_identity_max_length(self):
        """Test actual_identity respects max_length of 100."""
        from backend.api.schemas.feedback import EventFeedbackCreate, FeedbackType

        # Valid at max length
        feedback = EventFeedbackCreate(
            event_id=123,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            actual_identity="A" * 100,
        )
        assert len(feedback.actual_identity) == 100

        # Invalid over max length
        with pytest.raises(ValidationError) as exc_info:
            EventFeedbackCreate(
                event_id=123,
                feedback_type=FeedbackType.FALSE_POSITIVE,
                actual_identity="A" * 101,
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("actual_identity",) for e in errors)

    def test_create_with_what_was_wrong(self):
        """Test creating feedback with what_was_wrong."""
        from backend.api.schemas.feedback import EventFeedbackCreate, FeedbackType

        explanation = "The VQA model returned garbage tokens instead of clothing description."
        feedback = EventFeedbackCreate(
            event_id=123,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            what_was_wrong=explanation,
        )

        assert feedback.what_was_wrong == explanation

    def test_create_with_model_failures(self):
        """Test creating feedback with model_failures list."""
        from backend.api.schemas.feedback import EventFeedbackCreate, FeedbackType

        failures = ["florence_vqa", "pose_model"]
        feedback = EventFeedbackCreate(
            event_id=123,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            model_failures=failures,
        )

        assert feedback.model_failures == failures

    def test_create_with_empty_model_failures(self):
        """Test creating feedback with empty model_failures list."""
        from backend.api.schemas.feedback import EventFeedbackCreate, FeedbackType

        feedback = EventFeedbackCreate(
            event_id=123,
            feedback_type=FeedbackType.ACCURATE,
            model_failures=[],
        )

        assert feedback.model_failures == []

    def test_create_with_all_enhanced_fields(self):
        """Test creating feedback with all enhanced fields populated."""
        from backend.api.schemas.feedback import (
            ActualThreatLevel,
            EventFeedbackCreate,
            FeedbackType,
        )

        feedback = EventFeedbackCreate(
            event_id=123,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            notes="This was my neighbor",
            actual_threat_level=ActualThreatLevel.NO_THREAT,
            suggested_score=5,
            actual_identity="Mike (neighbor)",
            what_was_wrong="Re-ID should have matched this person",
            model_failures=["reid_model", "clothing_model"],
        )

        assert feedback.event_id == 123
        assert feedback.feedback_type == FeedbackType.FALSE_POSITIVE
        assert feedback.notes == "This was my neighbor"
        assert feedback.actual_threat_level == ActualThreatLevel.NO_THREAT
        assert feedback.suggested_score == 5
        assert feedback.actual_identity == "Mike (neighbor)"
        assert feedback.what_was_wrong == "Re-ID should have matched this person"
        assert feedback.model_failures == ["reid_model", "clothing_model"]

    def test_create_enhanced_fields_all_optional(self):
        """Test all enhanced fields are optional."""
        from backend.api.schemas.feedback import EventFeedbackCreate, FeedbackType

        feedback = EventFeedbackCreate(
            event_id=123,
            feedback_type=FeedbackType.FALSE_POSITIVE,
        )

        assert feedback.actual_threat_level is None
        assert feedback.suggested_score is None
        assert feedback.actual_identity is None
        assert feedback.what_was_wrong is None
        assert feedback.model_failures is None


# =============================================================================
# EventFeedbackResponse Tests
# =============================================================================


class TestEventFeedbackResponse:
    """Tests for EventFeedbackResponse schema."""

    def test_response_contains_all_fields(self):
        """Test response schema has all expected fields."""
        from datetime import UTC, datetime

        from backend.api.schemas.feedback import EventFeedbackResponse, FeedbackType

        now = datetime.now(UTC)
        response = EventFeedbackResponse(
            id=1,
            event_id=123,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            notes="Test notes",
            created_at=now,
        )

        assert response.id == 1
        assert response.event_id == 123
        assert response.feedback_type == FeedbackType.FALSE_POSITIVE
        assert response.notes == "Test notes"
        assert response.created_at == now

    def test_response_notes_can_be_none(self):
        """Test response handles None notes."""
        from datetime import UTC, datetime

        from backend.api.schemas.feedback import EventFeedbackResponse, FeedbackType

        response = EventFeedbackResponse(
            id=2,
            event_id=456,
            feedback_type=FeedbackType.MISSED_THREAT,
            notes=None,
            created_at=datetime.now(UTC),
        )

        assert response.notes is None

    def test_response_from_attributes(self):
        """Test response can be created from ORM model attributes."""
        from datetime import UTC, datetime
        from unittest.mock import MagicMock

        from backend.api.schemas.feedback import EventFeedbackResponse

        # Simulate ORM model
        mock_model = MagicMock()
        mock_model.id = 3
        mock_model.event_id = 789
        mock_model.feedback_type = "severity_wrong"
        mock_model.notes = "Severity too high"
        mock_model.created_at = datetime.now(UTC)

        response = EventFeedbackResponse.model_validate(mock_model)

        assert response.id == 3
        assert response.event_id == 789
        assert response.feedback_type == "severity_wrong"
        assert response.notes == "Severity too high"

    def test_response_serialization(self):
        """Test response serializes correctly to JSON-compatible dict."""
        from datetime import UTC, datetime

        from backend.api.schemas.feedback import EventFeedbackResponse, FeedbackType

        response = EventFeedbackResponse(
            id=4,
            event_id=100,
            feedback_type=FeedbackType.ACCURATE,
            notes=None,
            created_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        )

        data = response.model_dump(mode="json")

        assert data["id"] == 4
        assert data["event_id"] == 100
        assert data["feedback_type"] == "accurate"
        assert data["notes"] is None
        assert "created_at" in data


# =============================================================================
# EventFeedbackResponse Enhanced Fields Tests (NEM-3330)
# =============================================================================


class TestEventFeedbackResponseEnhanced:
    """Tests for EventFeedbackResponse enhanced fields (NEM-3330)."""

    def test_response_with_enhanced_fields(self):
        """Test response schema includes enhanced fields."""
        from datetime import UTC, datetime

        from backend.api.schemas.feedback import (
            ActualThreatLevel,
            EventFeedbackResponse,
            FeedbackType,
        )

        now = datetime.now(UTC)
        response = EventFeedbackResponse(
            id=1,
            event_id=123,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            notes="Test notes",
            actual_threat_level=ActualThreatLevel.NO_THREAT,
            suggested_score=10,
            actual_identity="Mike (neighbor)",
            what_was_wrong="Re-ID failed",
            model_failures=["reid_model"],
            created_at=now,
        )

        assert response.actual_threat_level == ActualThreatLevel.NO_THREAT
        assert response.suggested_score == 10
        assert response.actual_identity == "Mike (neighbor)"
        assert response.what_was_wrong == "Re-ID failed"
        assert response.model_failures == ["reid_model"]

    def test_response_enhanced_fields_default_to_none(self):
        """Test enhanced fields default to None."""
        from datetime import UTC, datetime

        from backend.api.schemas.feedback import EventFeedbackResponse, FeedbackType

        response = EventFeedbackResponse(
            id=1,
            event_id=123,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            notes=None,
            created_at=datetime.now(UTC),
        )

        assert response.actual_threat_level is None
        assert response.suggested_score is None
        assert response.actual_identity is None
        assert response.what_was_wrong is None
        assert response.model_failures is None

    def test_response_from_orm_with_enhanced_fields(self):
        """Test response can be created from ORM model with enhanced fields."""
        from datetime import UTC, datetime
        from unittest.mock import MagicMock

        from backend.api.schemas.feedback import EventFeedbackResponse

        # Simulate ORM model with enhanced fields
        mock_model = MagicMock()
        mock_model.id = 5
        mock_model.event_id = 500
        mock_model.feedback_type = "false_positive"
        mock_model.notes = "Neighbor's car"
        mock_model.actual_threat_level = "no_threat"
        mock_model.suggested_score = 5
        mock_model.actual_identity = "John Smith"
        mock_model.what_was_wrong = "Should have been identified as neighbor"
        mock_model.model_failures = ["reid_model", "florence_vqa"]
        mock_model.created_at = datetime.now(UTC)

        response = EventFeedbackResponse.model_validate(mock_model)

        assert response.id == 5
        assert response.event_id == 500
        assert response.actual_threat_level == "no_threat"
        assert response.suggested_score == 5
        assert response.actual_identity == "John Smith"
        assert response.what_was_wrong == "Should have been identified as neighbor"
        assert response.model_failures == ["reid_model", "florence_vqa"]

    def test_response_serialization_with_enhanced_fields(self):
        """Test response serializes enhanced fields correctly."""
        from datetime import UTC, datetime

        from backend.api.schemas.feedback import (
            ActualThreatLevel,
            EventFeedbackResponse,
            FeedbackType,
        )

        response = EventFeedbackResponse(
            id=6,
            event_id=600,
            feedback_type=FeedbackType.SEVERITY_WRONG,
            notes="Score too high",
            actual_threat_level=ActualThreatLevel.MINOR_CONCERN,
            suggested_score=35,
            actual_identity=None,
            what_was_wrong="Should not have been critical",
            model_failures=["pose_model"],
            created_at=datetime(2025, 1, 15, 14, 30, 0, tzinfo=UTC),
        )

        data = response.model_dump(mode="json")

        assert data["actual_threat_level"] == "minor_concern"
        assert data["suggested_score"] == 35
        assert data["actual_identity"] is None
        assert data["what_was_wrong"] == "Should not have been critical"
        assert data["model_failures"] == ["pose_model"]


# =============================================================================
# FeedbackStatsResponse Tests
# =============================================================================


class TestFeedbackStatsResponse:
    """Tests for FeedbackStatsResponse schema."""

    def test_stats_response_contains_expected_fields(self):
        """Test stats response has all expected aggregation fields."""
        from backend.api.schemas.feedback import FeedbackStatsResponse

        stats = FeedbackStatsResponse(
            total_feedback=100,
            by_type={
                "false_positive": 40,
                "missed_threat": 30,
                "severity_wrong": 20,
                "accurate": 10,
            },
            by_camera={
                "front_door": 50,
                "back_yard": 30,
                "garage": 20,
            },
        )

        assert stats.total_feedback == 100
        assert stats.by_type["false_positive"] == 40
        assert stats.by_type["missed_threat"] == 30
        assert stats.by_camera["front_door"] == 50

    def test_stats_response_empty_data(self):
        """Test stats response handles empty data."""
        from backend.api.schemas.feedback import FeedbackStatsResponse

        stats = FeedbackStatsResponse(
            total_feedback=0,
            by_type={},
            by_camera={},
        )

        assert stats.total_feedback == 0
        assert stats.by_type == {}
        assert stats.by_camera == {}

    def test_stats_response_total_must_be_non_negative(self):
        """Test total_feedback must be >= 0."""
        from backend.api.schemas.feedback import FeedbackStatsResponse

        with pytest.raises(ValidationError) as exc_info:
            FeedbackStatsResponse(
                total_feedback=-1,
                by_type={},
                by_camera={},
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("total_feedback",) for e in errors)

    def test_stats_response_serialization(self):
        """Test stats response serializes correctly."""
        from backend.api.schemas.feedback import FeedbackStatsResponse

        stats = FeedbackStatsResponse(
            total_feedback=50,
            by_type={"false_positive": 25, "accurate": 25},
            by_camera={"front_door": 50},
        )

        data = stats.model_dump(mode="json")

        assert data["total_feedback"] == 50
        assert data["by_type"] == {"false_positive": 25, "accurate": 25}
        assert data["by_camera"] == {"front_door": 50}

    def test_stats_response_has_example(self):
        """Test stats response schema has OpenAPI example."""
        from backend.api.schemas.feedback import FeedbackStatsResponse

        schema = FeedbackStatsResponse.model_json_schema()

        # Should have example in schema config
        assert (
            "examples" in schema
            or "example" in schema.get("properties", {}).get("total_feedback", {})
            or FeedbackStatsResponse.model_config.get("json_schema_extra") is not None
        )
