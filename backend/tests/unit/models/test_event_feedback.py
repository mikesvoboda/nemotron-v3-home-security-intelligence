"""Unit tests for EventFeedback model and FeedbackType enum.

Tests cover:
- FeedbackType enum values and string conversion
- EventFeedback model initialization and default values
- Field validation and constraints
- String representation (__repr__)
- expected_severity field for severity_wrong feedback
- Table indexes and constraints
- Property-based tests for field values

Related Linear issues: NEM-2348, NEM-2352
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
