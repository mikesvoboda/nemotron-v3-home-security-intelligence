"""Unit tests for Summary model.

Tests cover:
- SummaryType enum values and behavior
- Summary model initialization and fields
- Summary model __repr__ method
- Summary table configuration (name, indexes, constraints)
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect

from backend.models.summary import Summary, SummaryType

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# SummaryType Enum Tests
# =============================================================================


class TestSummaryType:
    """Tests for SummaryType enum."""

    def test_hourly_value(self) -> None:
        """Test HOURLY enum has correct string value."""
        assert SummaryType.HOURLY.value == "hourly"

    def test_daily_value(self) -> None:
        """Test DAILY enum has correct string value."""
        assert SummaryType.DAILY.value == "daily"

    def test_is_string_enum(self) -> None:
        """Test SummaryType inherits from str for JSON serialization."""
        assert isinstance(SummaryType.HOURLY, str)
        assert isinstance(SummaryType.DAILY, str)

    def test_enum_comparison_with_string(self) -> None:
        """Test enum values can be compared directly with strings."""
        assert SummaryType.HOURLY == "hourly"
        assert SummaryType.DAILY == "daily"

    def test_enum_count(self) -> None:
        """Test SummaryType has exactly two values."""
        assert len(SummaryType) == 2


# =============================================================================
# Summary Model Tests
# =============================================================================


class TestSummaryModel:
    """Tests for Summary model initialization and fields."""

    def test_create_summary_minimal(self) -> None:
        """Test creating a summary with required fields."""
        now = datetime.now(UTC)
        summary = Summary(
            summary_type=SummaryType.HOURLY.value,
            content="Test summary content",
            event_count=3,
            window_start=now,
            window_end=now,
            generated_at=now,
        )

        assert summary.summary_type == "hourly"
        assert summary.content == "Test summary content"
        assert summary.event_count == 3
        assert summary.window_start == now
        assert summary.window_end == now
        assert summary.generated_at == now
        assert summary.event_ids is None

    def test_create_summary_with_event_ids(self) -> None:
        """Test creating a summary with event_ids array."""
        now = datetime.now(UTC)
        event_ids = [1, 2, 3, 4, 5]
        summary = Summary(
            summary_type=SummaryType.DAILY.value,
            content="Daily summary with events",
            event_count=5,
            event_ids=event_ids,
            window_start=now,
            window_end=now,
            generated_at=now,
        )

        assert summary.summary_type == "daily"
        assert summary.event_ids == [1, 2, 3, 4, 5]
        assert summary.event_count == 5

    def test_create_summary_with_empty_event_ids(self) -> None:
        """Test creating a summary with empty event_ids list."""
        now = datetime.now(UTC)
        summary = Summary(
            summary_type=SummaryType.HOURLY.value,
            content="No events summary",
            event_count=0,
            event_ids=[],
            window_start=now,
            window_end=now,
            generated_at=now,
        )

        assert summary.event_ids == []
        assert summary.event_count == 0

    def test_summary_fields_roundtrip(self) -> None:
        """Test all fields roundtrip correctly."""
        window_start = datetime(2026, 1, 18, 14, 0, 0, tzinfo=UTC)
        window_end = datetime(2026, 1, 18, 15, 0, 0, tzinfo=UTC)
        generated_at = datetime(2026, 1, 18, 14, 55, 0, tzinfo=UTC)

        summary = Summary(
            summary_type=SummaryType.HOURLY.value,
            content="Over the past hour, one critical event occurred.",
            event_count=1,
            event_ids=[42],
            window_start=window_start,
            window_end=window_end,
            generated_at=generated_at,
        )

        assert summary.summary_type == "hourly"
        assert summary.content == "Over the past hour, one critical event occurred."
        assert summary.event_count == 1
        assert summary.event_ids == [42]
        assert summary.window_start == window_start
        assert summary.window_end == window_end
        assert summary.generated_at == generated_at


# =============================================================================
# Summary Repr Tests
# =============================================================================


class TestSummaryRepr:
    """Tests for Summary __repr__ method."""

    def test_repr_contains_class_name(self) -> None:
        """Test repr contains 'Summary'."""
        summary = Summary(
            id=1,
            summary_type="hourly",
            content="Test",
            event_count=5,
        )
        repr_str = repr(summary)
        assert "Summary" in repr_str

    def test_repr_contains_id(self) -> None:
        """Test repr contains the id value."""
        summary = Summary(
            id=42,
            summary_type="hourly",
            content="Test",
            event_count=3,
        )
        repr_str = repr(summary)
        assert "id=42" in repr_str

    def test_repr_contains_type(self) -> None:
        """Test repr contains the summary type."""
        summary = Summary(
            id=1,
            summary_type="daily",
            content="Test",
            event_count=10,
        )
        repr_str = repr(summary)
        assert "type=daily" in repr_str

    def test_repr_contains_event_count(self) -> None:
        """Test repr contains the event count."""
        summary = Summary(
            id=1,
            summary_type="hourly",
            content="Test",
            event_count=7,
        )
        repr_str = repr(summary)
        assert "events=7" in repr_str

    def test_repr_format(self) -> None:
        """Test repr has expected format."""
        summary = Summary(
            id=1,
            summary_type="hourly",
            content="Test",
            event_count=5,
        )
        repr_str = repr(summary)
        assert repr_str == "<Summary(id=1, type=hourly, events=5)>"


# =============================================================================
# Summary Table Configuration Tests
# =============================================================================


class TestSummaryTableConfiguration:
    """Tests for Summary table name, indexes, and constraints."""

    def test_tablename(self) -> None:
        """Test Summary has correct table name."""
        assert Summary.__tablename__ == "summaries"

    def test_has_table_args(self) -> None:
        """Test Summary model has __table_args__."""
        assert hasattr(Summary, "__table_args__")

    def test_indexes_defined(self) -> None:
        """Test Summary has expected indexes."""
        mapper = inspect(Summary)
        table = mapper.local_table
        index_names = [idx.name for idx in table.indexes]

        assert "idx_summaries_type_created" in index_names
        assert "idx_summaries_created_at" in index_names

    def test_check_constraint_defined(self) -> None:
        """Test Summary has check constraint for summary_type."""
        mapper = inspect(Summary)
        table = mapper.local_table
        constraint_names = [c.name for c in table.constraints if c.name]

        assert "summaries_type_check" in constraint_names

    def test_primary_key_column(self) -> None:
        """Test id is the primary key."""
        mapper = inspect(Summary)
        pk_columns = [col.name for col in mapper.primary_key]
        assert pk_columns == ["id"]

    def test_column_types(self) -> None:
        """Test columns have correct types."""
        mapper = inspect(Summary)
        columns = {col.name: col for col in mapper.columns}

        # Check nullable settings
        assert columns["id"].primary_key is True
        assert columns["summary_type"].nullable is False
        assert columns["content"].nullable is False
        assert columns["event_count"].nullable is False
        assert columns["event_ids"].nullable is True
        assert columns["window_start"].nullable is False
        assert columns["window_end"].nullable is False
        assert columns["generated_at"].nullable is False
        assert columns["created_at"].nullable is False

    def test_created_at_has_server_default(self) -> None:
        """Test created_at column has server_default."""
        mapper = inspect(Summary)
        created_at_col = mapper.columns["created_at"]
        assert created_at_col.server_default is not None


# =============================================================================
# Import Tests
# =============================================================================


class TestSummaryImports:
    """Tests for Summary model imports from models package."""

    def test_import_from_models_package(self) -> None:
        """Test Summary can be imported from backend.models."""
        from backend.models import Summary as ImportedSummary
        from backend.models import SummaryType as ImportedSummaryType

        assert ImportedSummary is Summary
        assert ImportedSummaryType is SummaryType

    def test_in_models_all(self) -> None:
        """Test Summary and SummaryType are in __all__."""
        from backend import models

        assert "Summary" in models.__all__
        assert "SummaryType" in models.__all__
