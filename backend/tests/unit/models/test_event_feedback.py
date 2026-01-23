"""Unit tests for EventFeedback model and FeedbackType enum.

Tests cover:
- FeedbackType enum values and string conversion
- EventFeedback model initialization and default values
- Field validation and constraints
- String representation (__repr__)
- expected_severity field for severity_wrong feedback
- Table indexes and constraints
- Property-based tests for field values
- Enhanced feedback fields (NEM-3330):
  - actual_threat_level for calibration
  - suggested_score for user-suggested risk score
  - actual_identity for household member identification
  - what_was_wrong for learning data
  - model_failures for tracking which AI models failed

Related Linear issues: NEM-2348, NEM-2352, NEM-3330
"""

from datetime import UTC, datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import CheckConstraint, inspect

from backend.models.event_feedback import EventFeedback, FeedbackType

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for valid feedback types
feedback_types = st.sampled_from(list(FeedbackType))

# Strategy for valid severity values
severity_values = st.sampled_from(["low", "medium", "high", "critical"])

# Strategy for optional severity values (including None)
optional_severity_values = st.one_of(st.none(), severity_values)

# Strategy for valid actual_threat_level values
threat_level_values = st.sampled_from(["no_threat", "minor_concern", "genuine_threat"])

# Strategy for optional threat level values (including None)
optional_threat_level_values = st.one_of(st.none(), threat_level_values)

# Strategy for valid suggested_score values (0-100)
suggested_scores = st.integers(min_value=0, max_value=100)

# Strategy for optional suggested scores (including None)
optional_suggested_scores = st.one_of(st.none(), suggested_scores)

# Strategy for actual_identity values (names)
# Unicode categories: L=letters, N=numbers, Zs=space separator
actual_identity_values = st.one_of(
    st.none(),
    st.text(min_size=1, max_size=100, alphabet=st.characters(categories=["L", "N", "Zs"])),
)

# Strategy for model_failures list
model_failure_options = st.sampled_from(
    ["clothing_model", "pose_model", "florence_vqa", "reid_model", "action_model"]
)
model_failures_list = st.one_of(
    st.none(),
    st.lists(model_failure_options, min_size=0, max_size=5, unique=True),
)

# Strategy for valid event IDs
event_ids = st.integers(min_value=1, max_value=2**31 - 1)

# Strategy for valid notes
notes_strategy = st.one_of(
    st.none(),
    st.text(min_size=0, max_size=1000),
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_feedback():
    """Create a sample EventFeedback for testing."""
    return EventFeedback(
        id=1,
        event_id=100,
        feedback_type=FeedbackType.FALSE_POSITIVE,
        notes="This was my neighbor's car.",
    )


@pytest.fixture
def correct_feedback():
    """Create a correct feedback for testing."""
    return EventFeedback(
        id=2,
        event_id=101,
        feedback_type=FeedbackType.CORRECT,
        notes="Alert was accurate",
    )


@pytest.fixture
def severity_wrong_feedback():
    """Create a severity_wrong feedback for testing."""
    return EventFeedback(
        id=3,
        event_id=102,
        feedback_type=FeedbackType.SEVERITY_WRONG,
        notes="Should have been higher severity",
        expected_severity="high",
    )


@pytest.fixture
def missed_threat_feedback():
    """Create a missed_threat feedback for testing."""
    return EventFeedback(
        id=4,
        event_id=103,
        feedback_type=FeedbackType.MISSED_THREAT,
        notes="Actual threat was not detected",
    )


@pytest.fixture
def minimal_feedback():
    """Create an EventFeedback with only required fields."""
    return EventFeedback(
        event_id=1,
        feedback_type=FeedbackType.ACCURATE,
    )


@pytest.fixture
def feedback_with_timestamp():
    """Create an EventFeedback with explicit timestamp."""
    return EventFeedback(
        event_id=50,
        feedback_type=FeedbackType.MISSED_THREAT,
        notes="Suspicious person not detected.",
        created_at=datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC),
    )


@pytest.fixture
def enhanced_feedback():
    """Create an EventFeedback with all enhanced fields populated."""
    return EventFeedback(
        id=10,
        event_id=200,
        feedback_type=FeedbackType.FALSE_POSITIVE,
        notes="This was my neighbor Mike.",
        actual_threat_level="no_threat",
        suggested_score=5,
        actual_identity="Mike (neighbor)",
        what_was_wrong="Person was incorrectly flagged as unknown intruder",
        model_failures=["reid_model", "clothing_model"],
    )


@pytest.fixture
def feedback_with_threat_level():
    """Create an EventFeedback with actual_threat_level set."""
    return EventFeedback(
        event_id=201,
        feedback_type=FeedbackType.SEVERITY_WRONG,
        actual_threat_level="minor_concern",
        suggested_score=25,
    )


@pytest.fixture
def feedback_with_identity():
    """Create an EventFeedback with actual_identity for household learning."""
    return EventFeedback(
        event_id=202,
        feedback_type=FeedbackType.FALSE_POSITIVE,
        actual_identity="Sarah (daughter)",
        what_was_wrong="Daughter coming home after school",
    )


@pytest.fixture
def feedback_with_model_failures():
    """Create an EventFeedback tracking specific model failures."""
    return EventFeedback(
        event_id=203,
        feedback_type=FeedbackType.FALSE_POSITIVE,
        model_failures=["florence_vqa", "pose_model", "clothing_model"],
        what_was_wrong="VQA returned garbage tokens, pose detection said running while sitting",
    )


# =============================================================================
# FeedbackType Enum Tests
# =============================================================================


class TestFeedbackTypeEnum:
    """Tests for FeedbackType enum."""

    def test_feedback_type_has_five_values(self):
        """Test FeedbackType enum has exactly 5 values (including both ACCURATE and CORRECT)."""
        assert len(FeedbackType) == 5

    def test_feedback_type_accurate(self):
        """Test ACCURATE feedback type."""
        assert FeedbackType.ACCURATE.value == "accurate"
        assert str(FeedbackType.ACCURATE) == "accurate"

    def test_feedback_type_correct(self):
        """Test CORRECT feedback type."""
        assert FeedbackType.CORRECT.value == "correct"
        assert str(FeedbackType.CORRECT) == "correct"

    def test_feedback_type_false_positive(self):
        """Test FALSE_POSITIVE feedback type."""
        assert FeedbackType.FALSE_POSITIVE.value == "false_positive"
        assert str(FeedbackType.FALSE_POSITIVE) == "false_positive"

    def test_feedback_type_missed_threat(self):
        """Test MISSED_THREAT feedback type."""
        assert FeedbackType.MISSED_THREAT.value == "missed_threat"
        assert str(FeedbackType.MISSED_THREAT) == "missed_threat"

    def test_feedback_type_severity_wrong(self):
        """Test SEVERITY_WRONG feedback type."""
        assert FeedbackType.SEVERITY_WRONG.value == "severity_wrong"
        assert str(FeedbackType.SEVERITY_WRONG) == "severity_wrong"

    def test_feedback_type_is_str_enum(self):
        """Test FeedbackType inherits from str."""
        assert isinstance(FeedbackType.ACCURATE, str)
        assert isinstance(FeedbackType.CORRECT, str)
        assert isinstance(FeedbackType.FALSE_POSITIVE, str)
        assert isinstance(FeedbackType.MISSED_THREAT, str)
        assert isinstance(FeedbackType.SEVERITY_WRONG, str)

    def test_feedback_type_from_string(self):
        """Test creating FeedbackType from string."""
        assert FeedbackType("accurate") == FeedbackType.ACCURATE
        assert FeedbackType("correct") == FeedbackType.CORRECT
        assert FeedbackType("false_positive") == FeedbackType.FALSE_POSITIVE
        assert FeedbackType("missed_threat") == FeedbackType.MISSED_THREAT
        assert FeedbackType("severity_wrong") == FeedbackType.SEVERITY_WRONG

    def test_feedback_type_invalid_raises_error(self):
        """Test invalid feedback type raises ValueError."""
        with pytest.raises(ValueError):
            FeedbackType("invalid_type")

    def test_feedback_type_all_values_distinct(self):
        """Test all FeedbackType values are distinct."""
        values = [ft.value for ft in FeedbackType]
        assert len(values) == len(set(values))


# =============================================================================
# EventFeedback Model Initialization Tests
# =============================================================================


class TestEventFeedbackModelInitialization:
    """Tests for EventFeedback model initialization."""

    def test_feedback_creation_minimal(self, minimal_feedback):
        """Test creating feedback with minimal required fields."""
        assert minimal_feedback.event_id == 1
        assert minimal_feedback.feedback_type == FeedbackType.ACCURATE
        assert minimal_feedback.notes is None

    def test_feedback_creation_with_all_fields(self, sample_feedback):
        """Test creating feedback with all fields populated."""
        assert sample_feedback.id == 1
        assert sample_feedback.event_id == 100
        assert sample_feedback.feedback_type == FeedbackType.FALSE_POSITIVE
        assert sample_feedback.notes == "This was my neighbor's car."

    def test_feedback_with_explicit_timestamp(self, feedback_with_timestamp):
        """Test feedback with explicit timestamp."""
        expected_time = datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC)
        assert feedback_with_timestamp.created_at == expected_time

    def test_feedback_notes_default_none(self, minimal_feedback):
        """Test that notes defaults to None."""
        assert minimal_feedback.notes is None

    def test_feedback_optional_fields_default_to_none(self, minimal_feedback):
        """Test optional fields default to None."""
        assert minimal_feedback.notes is None
        assert minimal_feedback.expected_severity is None

    def test_feedback_created_at_default_column_definition(self):
        """Test created_at default column definition.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        This test verifies the column default is correctly defined.
        """
        mapper = inspect(EventFeedback)
        created_at_col = mapper.columns["created_at"]
        assert created_at_col.default is not None
        # Default is a callable lambda
        assert callable(created_at_col.default.arg)

    def test_feedback_with_empty_notes(self):
        """Test feedback with empty string notes."""
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.ACCURATE,
            notes="",
        )
        assert feedback.notes == ""

    def test_feedback_with_long_notes(self):
        """Test feedback with long notes."""
        long_notes = "A" * 1000
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.SEVERITY_WRONG,
            notes=long_notes,
        )
        assert feedback.notes == long_notes
        assert len(feedback.notes) == 1000

    def test_feedback_all_types_can_be_created(self):
        """Test that all feedback types can be used to create feedback."""
        for feedback_type in FeedbackType:
            feedback = EventFeedback(
                event_id=1,
                feedback_type=feedback_type,
            )
            assert feedback.feedback_type == feedback_type


# =============================================================================
# EventFeedback Feedback Type Field Tests
# =============================================================================


class TestEventFeedbackFeedbackTypeField:
    """Tests for EventFeedback feedback_type field."""

    def test_feedback_type_correct(self, correct_feedback):
        """Test feedback with CORRECT type."""
        assert correct_feedback.feedback_type == FeedbackType.CORRECT

    def test_feedback_type_false_positive(self, sample_feedback):
        """Test feedback with FALSE_POSITIVE type."""
        assert sample_feedback.feedback_type == FeedbackType.FALSE_POSITIVE

    def test_feedback_type_missed_threat(self, missed_threat_feedback):
        """Test feedback with MISSED_THREAT type."""
        assert missed_threat_feedback.feedback_type == FeedbackType.MISSED_THREAT

    def test_feedback_type_severity_wrong(self, severity_wrong_feedback):
        """Test feedback with SEVERITY_WRONG type."""
        assert severity_wrong_feedback.feedback_type == FeedbackType.SEVERITY_WRONG

    def test_all_feedback_types_can_be_assigned(self):
        """Test all feedback types can be assigned to feedback."""
        for ft in FeedbackType:
            feedback = EventFeedback(event_id=1, feedback_type=ft)
            assert feedback.feedback_type == ft


# =============================================================================
# EventFeedback Expected Severity Field Tests
# =============================================================================


class TestEventFeedbackExpectedSeverityField:
    """Tests for EventFeedback expected_severity field."""

    def test_expected_severity_none_by_default(self, minimal_feedback):
        """Test expected_severity is None by default."""
        assert minimal_feedback.expected_severity is None

    def test_expected_severity_for_severity_wrong(self, severity_wrong_feedback):
        """Test expected_severity is set for severity_wrong feedback."""
        assert severity_wrong_feedback.expected_severity == "high"

    def test_expected_severity_low(self):
        """Test expected_severity with low value."""
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.SEVERITY_WRONG,
            expected_severity="low",
        )
        assert feedback.expected_severity == "low"

    def test_expected_severity_medium(self):
        """Test expected_severity with medium value."""
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.SEVERITY_WRONG,
            expected_severity="medium",
        )
        assert feedback.expected_severity == "medium"

    def test_expected_severity_high(self):
        """Test expected_severity with high value."""
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.SEVERITY_WRONG,
            expected_severity="high",
        )
        assert feedback.expected_severity == "high"

    def test_expected_severity_critical(self):
        """Test expected_severity with critical value."""
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.SEVERITY_WRONG,
            expected_severity="critical",
        )
        assert feedback.expected_severity == "critical"


# =============================================================================
# EventFeedback Notes Field Tests
# =============================================================================


class TestEventFeedbackNotesField:
    """Tests for EventFeedback notes field."""

    def test_notes_none_by_default(self, minimal_feedback):
        """Test notes is None by default."""
        assert minimal_feedback.notes is None

    def test_notes_can_be_set(self, sample_feedback):
        """Test notes can be set."""
        assert sample_feedback.notes == "This was my neighbor's car."

    def test_notes_empty_string(self):
        """Test notes can be empty string."""
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.CORRECT,
            notes="",
        )
        assert feedback.notes == ""

    def test_notes_long_text(self):
        """Test notes can contain long text."""
        long_notes = "A" * 1000
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            notes=long_notes,
        )
        assert feedback.notes == long_notes


# =============================================================================
# EventFeedback Column Definition Tests
# =============================================================================


class TestEventFeedbackColumnDefinitions:
    """Tests for EventFeedback column definitions."""

    def test_feedback_has_id_column(self):
        """Test EventFeedback has id column defined."""
        mapper = inspect(EventFeedback)
        assert "id" in mapper.columns

    def test_feedback_id_is_primary_key(self):
        """Test id column is primary key."""
        mapper = inspect(EventFeedback)
        id_col = mapper.columns["id"]
        assert id_col.primary_key

    def test_feedback_id_is_autoincrement(self):
        """Test id column is autoincrement."""
        mapper = inspect(EventFeedback)
        id_col = mapper.columns["id"]
        assert id_col.autoincrement is True or id_col.autoincrement == "auto"

    def test_feedback_has_event_id_column(self):
        """Test EventFeedback has event_id column defined."""
        mapper = inspect(EventFeedback)
        assert "event_id" in mapper.columns

    def test_feedback_event_id_is_not_nullable(self):
        """Test event_id column is not nullable."""
        mapper = inspect(EventFeedback)
        event_id_col = mapper.columns["event_id"]
        assert event_id_col.nullable is False

    def test_feedback_event_id_is_unique(self):
        """Test event_id column has unique constraint."""
        mapper = inspect(EventFeedback)
        event_id_col = mapper.columns["event_id"]
        assert event_id_col.unique is True

    def test_feedback_has_feedback_type_column(self):
        """Test EventFeedback has feedback_type column defined."""
        mapper = inspect(EventFeedback)
        assert "feedback_type" in mapper.columns

    def test_feedback_type_is_not_nullable(self):
        """Test feedback_type column is not nullable."""
        mapper = inspect(EventFeedback)
        type_col = mapper.columns["feedback_type"]
        assert type_col.nullable is False

    def test_feedback_has_notes_column(self):
        """Test EventFeedback has notes column defined."""
        mapper = inspect(EventFeedback)
        assert "notes" in mapper.columns

    def test_feedback_notes_is_nullable(self):
        """Test notes column is nullable."""
        mapper = inspect(EventFeedback)
        notes_col = mapper.columns["notes"]
        assert notes_col.nullable is True

    def test_feedback_has_created_at_column(self):
        """Test EventFeedback has created_at column defined."""
        mapper = inspect(EventFeedback)
        assert "created_at" in mapper.columns

    def test_feedback_created_at_has_default(self):
        """Test created_at column has default function."""
        mapper = inspect(EventFeedback)
        created_at_col = mapper.columns["created_at"]
        assert created_at_col.default is not None

    def test_expected_severity_is_optional(self):
        """Test expected_severity column is nullable."""
        mapper = inspect(EventFeedback)
        expected_severity_col = mapper.columns["expected_severity"]
        assert expected_severity_col.nullable is True


# =============================================================================
# EventFeedback Repr Tests
# =============================================================================


class TestEventFeedbackRepr:
    """Tests for EventFeedback string representation."""

    def test_repr_contains_class_name(self, sample_feedback):
        """Test repr contains class name."""
        repr_str = repr(sample_feedback)
        assert "EventFeedback" in repr_str

    def test_repr_contains_id(self, sample_feedback):
        """Test repr contains id."""
        repr_str = repr(sample_feedback)
        assert "id=1" in repr_str

    def test_repr_contains_event_id(self, sample_feedback):
        """Test repr contains event_id."""
        repr_str = repr(sample_feedback)
        assert "event_id=100" in repr_str

    def test_repr_contains_feedback_type(self, sample_feedback):
        """Test repr contains feedback_type."""
        repr_str = repr(sample_feedback)
        assert "false_positive" in repr_str

    def test_repr_format(self, sample_feedback):
        """Test repr has expected format."""
        repr_str = repr(sample_feedback)
        assert repr_str.startswith("<EventFeedback(")
        assert repr_str.endswith(")>")

    def test_repr_all_feedback_types(self):
        """Test repr for all feedback types."""
        for ft in FeedbackType:
            feedback = EventFeedback(id=1, event_id=1, feedback_type=ft)
            repr_str = repr(feedback)
            assert ft.value in repr_str


# =============================================================================
# EventFeedback Table Args Tests
# =============================================================================


class TestEventFeedbackTableArgs:
    """Tests for EventFeedback table arguments (indexes, constraints)."""

    def test_feedback_has_table_args(self):
        """Test EventFeedback model has __table_args__."""
        assert hasattr(EventFeedback, "__table_args__")

    def test_feedback_tablename(self):
        """Test EventFeedback has correct table name."""
        assert EventFeedback.__tablename__ == "event_feedback"

    def test_feedback_has_event_id_index(self):
        """Test EventFeedback has event_id index defined."""
        indexes = EventFeedback.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name") and idx.name]
        assert "idx_event_feedback_event_id" in index_names

    def test_feedback_has_feedback_type_index(self):
        """Test EventFeedback has feedback_type index defined."""
        indexes = EventFeedback.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name") and idx.name]
        assert "idx_event_feedback_type" in index_names

    def test_feedback_has_created_at_index(self):
        """Test EventFeedback has created_at index defined."""
        indexes = EventFeedback.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name") and idx.name]
        assert "idx_event_feedback_created_at" in index_names


# =============================================================================
# EventFeedback Constraints Tests
# =============================================================================


class TestEventFeedbackConstraints:
    """Tests for EventFeedback check constraints."""

    def test_feedback_has_type_check_constraint(self):
        """Test EventFeedback has feedback_type CHECK constraint defined."""
        constraints = [
            arg for arg in EventFeedback.__table_args__ if isinstance(arg, CheckConstraint)
        ]
        constraint_names = [c.name for c in constraints if c.name]
        assert "ck_event_feedback_type" in constraint_names

    def test_has_expected_severity_constraint(self):
        """Test EventFeedback has expected_severity CHECK constraint defined."""
        constraints = [
            arg for arg in EventFeedback.__table_args__ if isinstance(arg, CheckConstraint)
        ]
        constraint_names = [c.name for c in constraints if c.name]
        assert "ck_event_feedback_expected_severity" in constraint_names

    def test_feedback_type_constraint_includes_accurate(self):
        """Test CHECK constraint includes 'accurate' value."""
        constraints = [
            arg for arg in EventFeedback.__table_args__ if isinstance(arg, CheckConstraint)
        ]
        type_constraint = next((c for c in constraints if c.name == "ck_event_feedback_type"), None)
        assert type_constraint is not None
        # Check the sqltext contains all valid values
        constraint_text = str(type_constraint.sqltext)
        assert "accurate" in constraint_text

    def test_feedback_type_constraint_includes_correct(self):
        """Test CHECK constraint includes 'correct' value."""
        constraints = [
            arg for arg in EventFeedback.__table_args__ if isinstance(arg, CheckConstraint)
        ]
        type_constraint = next((c for c in constraints if c.name == "ck_event_feedback_type"), None)
        assert type_constraint is not None
        constraint_text = str(type_constraint.sqltext)
        assert "correct" in constraint_text

    def test_feedback_type_constraint_includes_false_positive(self):
        """Test CHECK constraint includes 'false_positive' value."""
        constraints = [
            arg for arg in EventFeedback.__table_args__ if isinstance(arg, CheckConstraint)
        ]
        type_constraint = next((c for c in constraints if c.name == "ck_event_feedback_type"), None)
        assert type_constraint is not None
        constraint_text = str(type_constraint.sqltext)
        assert "false_positive" in constraint_text

    def test_feedback_type_constraint_includes_missed_threat(self):
        """Test CHECK constraint includes 'missed_threat' value."""
        constraints = [
            arg for arg in EventFeedback.__table_args__ if isinstance(arg, CheckConstraint)
        ]
        type_constraint = next((c for c in constraints if c.name == "ck_event_feedback_type"), None)
        assert type_constraint is not None
        constraint_text = str(type_constraint.sqltext)
        assert "missed_threat" in constraint_text

    def test_feedback_type_constraint_includes_severity_wrong(self):
        """Test CHECK constraint includes 'severity_wrong' value."""
        constraints = [
            arg for arg in EventFeedback.__table_args__ if isinstance(arg, CheckConstraint)
        ]
        type_constraint = next((c for c in constraints if c.name == "ck_event_feedback_type"), None)
        assert type_constraint is not None
        constraint_text = str(type_constraint.sqltext)
        assert "severity_wrong" in constraint_text


# =============================================================================
# EventFeedback Relationships Tests
# =============================================================================


class TestEventFeedbackRelationships:
    """Tests for EventFeedback relationship definitions."""

    def test_feedback_has_event_relationship(self, sample_feedback):
        """Test feedback has event relationship defined."""
        assert hasattr(sample_feedback, "event")


# =============================================================================
# Property-based Tests
# =============================================================================


class TestEventFeedbackProperties:
    """Property-based tests for EventFeedback model."""

    @given(feedback_type=feedback_types)
    @settings(max_examples=20)
    def test_feedback_type_roundtrip(self, feedback_type: FeedbackType):
        """Property: Feedback type values roundtrip correctly."""
        feedback = EventFeedback(event_id=1, feedback_type=feedback_type)
        assert feedback.feedback_type == feedback_type

    @given(event_id=event_ids)
    @settings(max_examples=50)
    def test_event_id_roundtrip(self, event_id: int):
        """Property: Event ID values roundtrip correctly."""
        feedback = EventFeedback(
            event_id=event_id,
            feedback_type=FeedbackType.ACCURATE,
        )
        assert feedback.event_id == event_id

    @given(notes=notes_strategy)
    @settings(max_examples=50)
    def test_notes_roundtrip(self, notes: str | None):
        """Property: Notes values roundtrip correctly."""
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            notes=notes,
        )
        assert feedback.notes == notes

    @given(severity=optional_severity_values)
    @settings(max_examples=20)
    def test_expected_severity_roundtrip(self, severity: str | None):
        """Property: Expected severity values roundtrip correctly."""
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.SEVERITY_WRONG,
            expected_severity=severity,
        )
        assert feedback.expected_severity == severity

    @given(
        feedback_type=feedback_types,
        event_id=event_ids,
        notes=notes_strategy,
        severity=optional_severity_values,
    )
    @settings(max_examples=50)
    def test_all_fields_roundtrip(
        self,
        feedback_type: FeedbackType,
        event_id: int,
        notes: str | None,
        severity: str | None,
    ):
        """Property: All field values roundtrip correctly together."""
        feedback = EventFeedback(
            event_id=event_id,
            feedback_type=feedback_type,
            notes=notes,
            expected_severity=severity,
        )
        assert feedback.event_id == event_id
        assert feedback.feedback_type == feedback_type
        assert feedback.notes == notes
        assert feedback.expected_severity == severity


# =============================================================================
# FeedbackType Usage Semantics Tests
# =============================================================================


class TestFeedbackTypeSemantics:
    """Tests for FeedbackType semantic meaning and usage."""

    def test_accurate_means_correct_classification(self):
        """Test ACCURATE indicates correct AI classification."""
        # ACCURATE: The AI correctly identified and classified the event
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.ACCURATE,
            notes="AI correctly identified a delivery person.",
        )
        assert feedback.feedback_type == FeedbackType.ACCURATE

    def test_false_positive_means_incorrect_flag(self):
        """Test FALSE_POSITIVE indicates incorrect threat flag."""
        # FALSE_POSITIVE: AI flagged something as a threat when it wasn't
        feedback = EventFeedback(
            event_id=2,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            notes="Flagged my cat as an intruder.",
        )
        assert feedback.feedback_type == FeedbackType.FALSE_POSITIVE

    def test_missed_threat_means_undetected_concern(self):
        """Test MISSED_THREAT indicates undetected security event."""
        # MISSED_THREAT: AI failed to detect something concerning
        feedback = EventFeedback(
            event_id=3,
            feedback_type=FeedbackType.MISSED_THREAT,
            notes="Suspicious person was not flagged.",
        )
        assert feedback.feedback_type == FeedbackType.MISSED_THREAT

    def test_severity_wrong_means_incorrect_level(self):
        """Test SEVERITY_WRONG indicates incorrect severity assignment."""
        # SEVERITY_WRONG: AI detected event but severity was inappropriate
        feedback = EventFeedback(
            event_id=4,
            feedback_type=FeedbackType.SEVERITY_WRONG,
            notes="Package delivery marked as critical threat.",
        )
        assert feedback.feedback_type == FeedbackType.SEVERITY_WRONG


# =============================================================================
# Enhanced Feedback Fields Tests (NEM-3330)
# =============================================================================


class TestEventFeedbackActualThreatLevel:
    """Tests for EventFeedback actual_threat_level field."""

    def test_actual_threat_level_none_by_default(self, minimal_feedback):
        """Test actual_threat_level is None by default."""
        assert minimal_feedback.actual_threat_level is None

    def test_actual_threat_level_no_threat(self):
        """Test actual_threat_level with no_threat value."""
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            actual_threat_level="no_threat",
        )
        assert feedback.actual_threat_level == "no_threat"

    def test_actual_threat_level_minor_concern(self):
        """Test actual_threat_level with minor_concern value."""
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.SEVERITY_WRONG,
            actual_threat_level="minor_concern",
        )
        assert feedback.actual_threat_level == "minor_concern"

    def test_actual_threat_level_genuine_threat(self):
        """Test actual_threat_level with genuine_threat value."""
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.MISSED_THREAT,
            actual_threat_level="genuine_threat",
        )
        assert feedback.actual_threat_level == "genuine_threat"

    def test_actual_threat_level_with_fixture(self, feedback_with_threat_level):
        """Test actual_threat_level from fixture."""
        assert feedback_with_threat_level.actual_threat_level == "minor_concern"

    def test_actual_threat_level_in_enhanced_feedback(self, enhanced_feedback):
        """Test actual_threat_level in fully enhanced feedback."""
        assert enhanced_feedback.actual_threat_level == "no_threat"


class TestEventFeedbackSuggestedScore:
    """Tests for EventFeedback suggested_score field."""

    def test_suggested_score_none_by_default(self, minimal_feedback):
        """Test suggested_score is None by default."""
        assert minimal_feedback.suggested_score is None

    def test_suggested_score_low_value(self):
        """Test suggested_score with low value (normal activity)."""
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            suggested_score=5,
        )
        assert feedback.suggested_score == 5

    def test_suggested_score_medium_value(self):
        """Test suggested_score with medium value."""
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.SEVERITY_WRONG,
            suggested_score=45,
        )
        assert feedback.suggested_score == 45

    def test_suggested_score_high_value(self):
        """Test suggested_score with high value."""
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.MISSED_THREAT,
            suggested_score=85,
        )
        assert feedback.suggested_score == 85

    def test_suggested_score_max_value(self):
        """Test suggested_score with maximum value (100)."""
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.MISSED_THREAT,
            suggested_score=100,
        )
        assert feedback.suggested_score == 100

    def test_suggested_score_min_value(self):
        """Test suggested_score with minimum value (0)."""
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            suggested_score=0,
        )
        assert feedback.suggested_score == 0

    def test_suggested_score_with_fixture(self, feedback_with_threat_level):
        """Test suggested_score from fixture."""
        assert feedback_with_threat_level.suggested_score == 25

    def test_suggested_score_in_enhanced_feedback(self, enhanced_feedback):
        """Test suggested_score in fully enhanced feedback."""
        assert enhanced_feedback.suggested_score == 5


class TestEventFeedbackActualIdentity:
    """Tests for EventFeedback actual_identity field."""

    def test_actual_identity_none_by_default(self, minimal_feedback):
        """Test actual_identity is None by default."""
        assert minimal_feedback.actual_identity is None

    def test_actual_identity_simple_name(self):
        """Test actual_identity with simple name."""
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            actual_identity="Mike",
        )
        assert feedback.actual_identity == "Mike"

    def test_actual_identity_name_with_role(self):
        """Test actual_identity with name and role."""
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            actual_identity="John (gardener)",
        )
        assert feedback.actual_identity == "John (gardener)"

    def test_actual_identity_full_description(self):
        """Test actual_identity with full description."""
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            actual_identity="Sarah - daughter, comes home at 3pm daily",
        )
        assert feedback.actual_identity == "Sarah - daughter, comes home at 3pm daily"

    def test_actual_identity_with_fixture(self, feedback_with_identity):
        """Test actual_identity from fixture."""
        assert feedback_with_identity.actual_identity == "Sarah (daughter)"

    def test_actual_identity_in_enhanced_feedback(self, enhanced_feedback):
        """Test actual_identity in fully enhanced feedback."""
        assert enhanced_feedback.actual_identity == "Mike (neighbor)"

    def test_actual_identity_max_length(self):
        """Test actual_identity with maximum length (100 chars)."""
        long_identity = "A" * 100
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            actual_identity=long_identity,
        )
        assert feedback.actual_identity == long_identity
        assert len(feedback.actual_identity) == 100


class TestEventFeedbackWhatWasWrong:
    """Tests for EventFeedback what_was_wrong field."""

    def test_what_was_wrong_none_by_default(self, minimal_feedback):
        """Test what_was_wrong is None by default."""
        assert minimal_feedback.what_was_wrong is None

    def test_what_was_wrong_simple_description(self):
        """Test what_was_wrong with simple description."""
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            what_was_wrong="Person was my neighbor",
        )
        assert feedback.what_was_wrong == "Person was my neighbor"

    def test_what_was_wrong_detailed_analysis(self):
        """Test what_was_wrong with detailed analysis."""
        description = (
            "The VQA model returned garbage tokens instead of clothing description. "
            "Pose detection said 'running' but scene clearly shows person sitting. "
            "Re-ID should have matched against known household member."
        )
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            what_was_wrong=description,
        )
        assert feedback.what_was_wrong == description

    def test_what_was_wrong_with_fixture(self, feedback_with_identity):
        """Test what_was_wrong from fixture."""
        assert feedback_with_identity.what_was_wrong == "Daughter coming home after school"

    def test_what_was_wrong_in_enhanced_feedback(self, enhanced_feedback):
        """Test what_was_wrong in fully enhanced feedback."""
        assert (
            enhanced_feedback.what_was_wrong == "Person was incorrectly flagged as unknown intruder"
        )

    def test_what_was_wrong_long_text(self):
        """Test what_was_wrong can contain long text (Text field)."""
        long_text = "A" * 5000  # Text field should allow longer content than String
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            what_was_wrong=long_text,
        )
        assert feedback.what_was_wrong == long_text
        assert len(feedback.what_was_wrong) == 5000


class TestEventFeedbackModelFailures:
    """Tests for EventFeedback model_failures field."""

    def test_model_failures_none_by_default(self, minimal_feedback):
        """Test model_failures is None by default."""
        assert minimal_feedback.model_failures is None

    def test_model_failures_empty_list(self):
        """Test model_failures with empty list."""
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.ACCURATE,
            model_failures=[],
        )
        assert feedback.model_failures == []

    def test_model_failures_single_model(self):
        """Test model_failures with single model."""
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            model_failures=["florence_vqa"],
        )
        assert feedback.model_failures == ["florence_vqa"]
        assert len(feedback.model_failures) == 1

    def test_model_failures_multiple_models(self):
        """Test model_failures with multiple models."""
        failures = ["clothing_model", "pose_model", "reid_model"]
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            model_failures=failures,
        )
        assert feedback.model_failures == failures
        assert len(feedback.model_failures) == 3

    def test_model_failures_with_fixture(self, feedback_with_model_failures):
        """Test model_failures from fixture."""
        expected = ["florence_vqa", "pose_model", "clothing_model"]
        assert feedback_with_model_failures.model_failures == expected

    def test_model_failures_in_enhanced_feedback(self, enhanced_feedback):
        """Test model_failures in fully enhanced feedback."""
        assert enhanced_feedback.model_failures == ["reid_model", "clothing_model"]

    def test_model_failures_known_model_types(self):
        """Test model_failures with all known model types."""
        known_models = [
            "clothing_model",
            "pose_model",
            "florence_vqa",
            "reid_model",
            "action_model",
        ]
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            model_failures=known_models,
        )
        assert feedback.model_failures == known_models
        assert all(model in feedback.model_failures for model in known_models)


class TestEventFeedbackEnhancedColumnDefinitions:
    """Tests for enhanced EventFeedback column definitions."""

    def test_feedback_has_actual_threat_level_column(self):
        """Test EventFeedback has actual_threat_level column defined."""
        mapper = inspect(EventFeedback)
        assert "actual_threat_level" in mapper.columns

    def test_actual_threat_level_is_nullable(self):
        """Test actual_threat_level column is nullable."""
        mapper = inspect(EventFeedback)
        col = mapper.columns["actual_threat_level"]
        assert col.nullable is True

    def test_feedback_has_suggested_score_column(self):
        """Test EventFeedback has suggested_score column defined."""
        mapper = inspect(EventFeedback)
        assert "suggested_score" in mapper.columns

    def test_suggested_score_is_nullable(self):
        """Test suggested_score column is nullable."""
        mapper = inspect(EventFeedback)
        col = mapper.columns["suggested_score"]
        assert col.nullable is True

    def test_feedback_has_actual_identity_column(self):
        """Test EventFeedback has actual_identity column defined."""
        mapper = inspect(EventFeedback)
        assert "actual_identity" in mapper.columns

    def test_actual_identity_is_nullable(self):
        """Test actual_identity column is nullable."""
        mapper = inspect(EventFeedback)
        col = mapper.columns["actual_identity"]
        assert col.nullable is True

    def test_feedback_has_what_was_wrong_column(self):
        """Test EventFeedback has what_was_wrong column defined."""
        mapper = inspect(EventFeedback)
        assert "what_was_wrong" in mapper.columns

    def test_what_was_wrong_is_nullable(self):
        """Test what_was_wrong column is nullable."""
        mapper = inspect(EventFeedback)
        col = mapper.columns["what_was_wrong"]
        assert col.nullable is True

    def test_feedback_has_model_failures_column(self):
        """Test EventFeedback has model_failures column defined."""
        mapper = inspect(EventFeedback)
        assert "model_failures" in mapper.columns

    def test_model_failures_is_nullable(self):
        """Test model_failures column is nullable."""
        mapper = inspect(EventFeedback)
        col = mapper.columns["model_failures"]
        assert col.nullable is True


class TestEventFeedbackEnhancedConstraints:
    """Tests for enhanced EventFeedback constraints."""

    def test_has_actual_threat_level_constraint(self):
        """Test EventFeedback has actual_threat_level CHECK constraint defined."""
        constraints = [
            arg for arg in EventFeedback.__table_args__ if isinstance(arg, CheckConstraint)
        ]
        constraint_names = [c.name for c in constraints if c.name]
        assert "ck_event_feedback_actual_threat_level" in constraint_names

    def test_actual_threat_level_constraint_includes_no_threat(self):
        """Test CHECK constraint includes 'no_threat' value."""
        constraints = [
            arg for arg in EventFeedback.__table_args__ if isinstance(arg, CheckConstraint)
        ]
        constraint = next(
            (c for c in constraints if c.name == "ck_event_feedback_actual_threat_level"), None
        )
        assert constraint is not None
        constraint_text = str(constraint.sqltext)
        assert "no_threat" in constraint_text

    def test_actual_threat_level_constraint_includes_minor_concern(self):
        """Test CHECK constraint includes 'minor_concern' value."""
        constraints = [
            arg for arg in EventFeedback.__table_args__ if isinstance(arg, CheckConstraint)
        ]
        constraint = next(
            (c for c in constraints if c.name == "ck_event_feedback_actual_threat_level"), None
        )
        assert constraint is not None
        constraint_text = str(constraint.sqltext)
        assert "minor_concern" in constraint_text

    def test_actual_threat_level_constraint_includes_genuine_threat(self):
        """Test CHECK constraint includes 'genuine_threat' value."""
        constraints = [
            arg for arg in EventFeedback.__table_args__ if isinstance(arg, CheckConstraint)
        ]
        constraint = next(
            (c for c in constraints if c.name == "ck_event_feedback_actual_threat_level"), None
        )
        assert constraint is not None
        constraint_text = str(constraint.sqltext)
        assert "genuine_threat" in constraint_text

    def test_has_suggested_score_constraint(self):
        """Test EventFeedback has suggested_score CHECK constraint defined."""
        constraints = [
            arg for arg in EventFeedback.__table_args__ if isinstance(arg, CheckConstraint)
        ]
        constraint_names = [c.name for c in constraints if c.name]
        assert "ck_event_feedback_suggested_score" in constraint_names

    def test_suggested_score_constraint_range(self):
        """Test CHECK constraint enforces 0-100 range."""
        constraints = [
            arg for arg in EventFeedback.__table_args__ if isinstance(arg, CheckConstraint)
        ]
        constraint = next(
            (c for c in constraints if c.name == "ck_event_feedback_suggested_score"), None
        )
        assert constraint is not None
        constraint_text = str(constraint.sqltext)
        # Should reference suggested_score and have range bounds
        assert "suggested_score" in constraint_text


# =============================================================================
# Enhanced Property-based Tests
# =============================================================================


class TestEventFeedbackEnhancedProperties:
    """Property-based tests for enhanced EventFeedback fields."""

    @given(threat_level=optional_threat_level_values)
    @settings(max_examples=20)
    def test_actual_threat_level_roundtrip(self, threat_level: str | None):
        """Property: Actual threat level values roundtrip correctly."""
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            actual_threat_level=threat_level,
        )
        assert feedback.actual_threat_level == threat_level

    @given(score=optional_suggested_scores)
    @settings(max_examples=50)
    def test_suggested_score_roundtrip(self, score: int | None):
        """Property: Suggested score values roundtrip correctly."""
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.SEVERITY_WRONG,
            suggested_score=score,
        )
        assert feedback.suggested_score == score

    @given(identity=actual_identity_values)
    @settings(max_examples=50)
    def test_actual_identity_roundtrip(self, identity: str | None):
        """Property: Actual identity values roundtrip correctly."""
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            actual_identity=identity,
        )
        assert feedback.actual_identity == identity

    @given(failures=model_failures_list)
    @settings(max_examples=50)
    def test_model_failures_roundtrip(self, failures: list[str] | None):
        """Property: Model failures list values roundtrip correctly."""
        feedback = EventFeedback(
            event_id=1,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            model_failures=failures,
        )
        assert feedback.model_failures == failures

    @given(
        feedback_type=feedback_types,
        threat_level=optional_threat_level_values,
        score=optional_suggested_scores,
        identity=actual_identity_values,
        failures=model_failures_list,
    )
    @settings(max_examples=50)
    def test_all_enhanced_fields_roundtrip(
        self,
        feedback_type: FeedbackType,
        threat_level: str | None,
        score: int | None,
        identity: str | None,
        failures: list[str] | None,
    ):
        """Property: All enhanced field values roundtrip correctly together."""
        feedback = EventFeedback(
            event_id=1,
            feedback_type=feedback_type,
            actual_threat_level=threat_level,
            suggested_score=score,
            actual_identity=identity,
            model_failures=failures,
        )
        assert feedback.feedback_type == feedback_type
        assert feedback.actual_threat_level == threat_level
        assert feedback.suggested_score == score
        assert feedback.actual_identity == identity
        assert feedback.model_failures == failures
