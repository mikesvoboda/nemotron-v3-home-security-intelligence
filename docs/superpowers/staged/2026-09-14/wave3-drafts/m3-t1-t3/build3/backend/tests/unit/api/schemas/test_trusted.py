"""Tests for trusted data construction utilities (NEM-3430)."""

from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import BaseModel, Field

from backend.api.schemas.trusted import (
    from_db_record,
    from_db_records,
    from_dict,
)


class SampleResponse(BaseModel):
    """Sample Pydantic model for testing."""

    id: int
    name: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)


@dataclass
class MockORMRecord:
    """Mock ORM record for testing."""

    id: int
    name: str
    description: str | None = None
    tags: list[str] | None = None


class TestFromDbRecord:
    """Tests for from_db_record function."""

    def test_basic_construction(self):
        """Test basic model construction from ORM record."""
        record = MockORMRecord(id=1, name="Test", description="A test item")
        result = from_db_record(SampleResponse, record)

        assert isinstance(result, SampleResponse)
        assert result.id == 1
        assert result.name == "Test"
        assert result.description == "A test item"

    def test_missing_optional_field(self):
        """Test construction when optional field is missing from record."""
        record = MockORMRecord(id=1, name="Test")
        result = from_db_record(SampleResponse, record)

        assert result.id == 1
        assert result.name == "Test"
        assert result.description is None

    def test_with_update_dict(self):
        """Test construction with additional update values."""
        record = MockORMRecord(id=1, name="Test")
        result = from_db_record(
            SampleResponse,
            record,
            update={"description": "Added via update"},
        )

        assert result.id == 1
        assert result.name == "Test"
        assert result.description == "Added via update"

    def test_update_overrides_record(self):
        """Test that update values override record values."""
        record = MockORMRecord(id=1, name="Original")
        result = from_db_record(
            SampleResponse,
            record,
            update={"name": "Overridden"},
        )

        assert result.name == "Overridden"

    def test_update_ignores_none_by_default(self):
        """Test that None values in update are ignored by default."""
        record = MockORMRecord(id=1, name="Test", description="Original")
        result = from_db_record(
            SampleResponse,
            record,
            update={"description": None},
        )

        assert result.description == "Original"

    def test_update_includes_none_when_enabled(self):
        """Test that None values in update are included when include_none=True."""
        record = MockORMRecord(id=1, name="Test", description="Original")
        result = from_db_record(
            SampleResponse,
            record,
            update={"description": None},
            include_none=True,
        )

        assert result.description is None

    def test_from_dict_record(self):
        """Test construction from dictionary instead of ORM record."""
        record = {"id": 1, "name": "Test", "description": "From dict"}
        result = from_db_record(SampleResponse, record)

        assert result.id == 1
        assert result.name == "Test"
        assert result.description == "From dict"

    def test_ignores_extra_fields_in_record(self):
        """Test that extra fields in record are ignored."""
        record = {"id": 1, "name": "Test", "extra_field": "Should be ignored"}
        result = from_db_record(SampleResponse, record)

        assert result.id == 1
        assert result.name == "Test"
        assert not hasattr(result, "extra_field")


class TestFromDict:
    """Tests for from_dict function."""

    def test_basic_construction(self):
        """Test basic model construction from dictionary."""
        data = {"id": 1, "name": "Test", "description": "A test"}
        result = from_dict(SampleResponse, data)

        assert isinstance(result, SampleResponse)
        assert result.id == 1
        assert result.name == "Test"
        assert result.description == "A test"

    def test_with_fields_set(self):
        """Test construction with explicit fields_set."""
        data = {"id": 1, "name": "Test", "description": None}
        result = from_dict(
            SampleResponse,
            data,
            _fields_set={"id", "name"},
        )

        # The model should be created, but fields_set affects serialization
        assert result.id == 1
        assert result.name == "Test"

    def test_partial_data(self):
        """Test construction with partial data."""
        data = {"id": 1, "name": "Test"}
        result = from_dict(SampleResponse, data)

        assert result.id == 1
        assert result.name == "Test"
        assert result.description is None


class TestFromDbRecords:
    """Tests for from_db_records batch function."""

    def test_basic_batch_construction(self):
        """Test batch construction from multiple records."""
        records = [
            MockORMRecord(id=1, name="Item 1"),
            MockORMRecord(id=2, name="Item 2"),
            MockORMRecord(id=3, name="Item 3"),
        ]
        results = from_db_records(SampleResponse, records)

        assert len(results) == 3
        assert all(isinstance(r, SampleResponse) for r in results)
        assert results[0].id == 1
        assert results[1].id == 2
        assert results[2].id == 3

    def test_batch_with_update_function(self):
        """Test batch construction with update function."""
        records = [
            MockORMRecord(id=1, name="Item 1"),
            MockORMRecord(id=2, name="Item 2"),
        ]

        def add_thumbnail(record: MockORMRecord) -> dict[str, Any]:
            return {"description": f"Thumbnail for {record.id}"}

        results = from_db_records(SampleResponse, records, update_fn=add_thumbnail)

        assert results[0].description == "Thumbnail for 1"
        assert results[1].description == "Thumbnail for 2"

    def test_empty_records_list(self):
        """Test batch construction with empty list."""
        results = from_db_records(SampleResponse, [])

        assert results == []


class TestModelConstructPerformance:
    """Tests to verify model_construct behavior (no validation)."""

    def test_bypasses_validation(self):
        """Test that model_construct bypasses validation.

        Note: This is an important characteristic of model_construct - it does NOT
        run validators. This test documents that behavior.
        """

        # Create a model with stricter validation
        class StrictModel(BaseModel):
            id: int = Field(..., ge=1)  # Must be >= 1
            name: str = Field(..., min_length=1)  # Must be non-empty

        # Using regular construction with invalid data would fail
        with pytest.raises(Exception):
            StrictModel(id=0, name="")  # Both invalid

        # Using model_construct bypasses validation
        # WARNING: This is intentional behavior for trusted data only!
        # Invalid values CAN be constructed this way
        result = StrictModel.model_construct(id=0, name="")
        assert result.id == 0  # Normally invalid
        assert result.name == ""  # Normally invalid

    def test_from_db_record_preserves_construct_behavior(self):
        """Test that from_db_record uses model_construct (no validation)."""

        class StrictModel(BaseModel):
            id: int = Field(..., ge=1)
            name: str = Field(..., min_length=1)

        # from_db_record should also bypass validation (since it uses model_construct)
        record = {"id": 0, "name": ""}
        result = from_db_record(StrictModel, record)

        # This demonstrates why from_db_record should only be used with trusted data
        assert result.id == 0
        assert result.name == ""
