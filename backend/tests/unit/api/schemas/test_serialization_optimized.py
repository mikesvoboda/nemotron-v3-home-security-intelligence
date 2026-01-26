"""Unit tests for optimized serialization utilities (NEM-3776).

Tests verify that mode='json' serialization produces correct JSON-compatible
output and that utility functions work correctly.
"""

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel

from backend.api.schemas.serialization import (
    SerializationMixin,
    serialize_for_detail_view,
    serialize_for_list_view,
    serialize_list,
    serialize_response,
)


class StatusEnum(str, Enum):
    """Test enum for serialization tests."""

    ACTIVE = "active"
    INACTIVE = "inactive"


class SampleModel(BaseModel):
    """Sample model for serialization tests."""

    id: int
    name: str
    created_at: datetime
    status: StatusEnum = StatusEnum.ACTIVE
    optional_field: str | None = None
    large_field: str | None = None


class SampleMixinModel(SerializationMixin, BaseModel):
    """Sample model with serialization mixin."""

    id: int
    name: str
    created_at: datetime
    llm_prompt: str | None = None
    reasoning: str | None = None


class TestSerializeResponse:
    """Tests for serialize_response function."""

    def test_serializes_datetime_to_string(self):
        """Test that datetime is serialized to ISO string."""
        model = SampleModel(
            id=1,
            name="Test",
            created_at=datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC),
        )
        result = serialize_response(model)

        assert result["created_at"] == "2025-01-15T12:00:00Z"
        assert isinstance(result["created_at"], str)

    def test_serializes_enum_to_value(self):
        """Test that enum is serialized to its value."""
        model = SampleModel(
            id=1,
            name="Test",
            created_at=datetime.now(UTC),
            status=StatusEnum.ACTIVE,
        )
        result = serialize_response(model)

        assert result["status"] == "active"
        assert isinstance(result["status"], str)

    def test_excludes_none_by_default(self):
        """Test that None values are excluded by default."""
        model = SampleModel(
            id=1,
            name="Test",
            created_at=datetime.now(UTC),
            optional_field=None,
        )
        result = serialize_response(model)

        assert "optional_field" not in result

    def test_includes_none_when_requested(self):
        """Test that None values are included when exclude_none=False."""
        model = SampleModel(
            id=1,
            name="Test",
            created_at=datetime.now(UTC),
            optional_field=None,
        )
        result = serialize_response(model, exclude_none=False)

        assert "optional_field" in result
        assert result["optional_field"] is None

    def test_excludes_specified_fields(self):
        """Test that specified fields are excluded."""
        model = SampleModel(
            id=1,
            name="Test",
            created_at=datetime.now(UTC),
            large_field="large content",
        )
        result = serialize_response(model, exclude={"large_field"})

        assert "large_field" not in result
        assert "id" in result

    def test_includes_only_specified_fields(self):
        """Test that only specified fields are included."""
        model = SampleModel(
            id=1,
            name="Test",
            created_at=datetime.now(UTC),
            large_field="large content",
        )
        result = serialize_response(model, include={"id", "name"})

        assert "id" in result
        assert "name" in result
        assert "created_at" not in result
        assert "large_field" not in result


class TestSerializeList:
    """Tests for serialize_list function."""

    def test_serializes_list_of_models(self):
        """Test serialization of multiple models."""
        models = [
            SampleModel(id=1, name="First", created_at=datetime.now(UTC)),
            SampleModel(id=2, name="Second", created_at=datetime.now(UTC)),
        ]
        result = serialize_list(models)

        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[1]["id"] == 2

    def test_serializes_datetimes_in_list(self):
        """Test that datetimes are serialized to strings in list."""
        models = [
            SampleModel(
                id=1,
                name="Test",
                created_at=datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC),
            )
        ]
        result = serialize_list(models)

        assert result[0]["created_at"] == "2025-01-15T12:00:00Z"

    def test_excludes_fields_from_all_items(self):
        """Test that excluded fields are removed from all items."""
        models = [
            SampleModel(id=1, name="First", created_at=datetime.now(UTC), large_field="a"),
            SampleModel(id=2, name="Second", created_at=datetime.now(UTC), large_field="b"),
        ]
        result = serialize_list(models, exclude={"large_field"})

        assert "large_field" not in result[0]
        assert "large_field" not in result[1]

    def test_handles_empty_list(self):
        """Test serialization of empty list."""
        result = serialize_list([])
        assert result == []


class TestSerializeForListView:
    """Tests for serialize_for_list_view function."""

    def test_excludes_default_detail_fields(self):
        """Test that default detail fields are excluded."""

        class DetailModel(BaseModel):
            id: int
            name: str
            llm_prompt: str | None = None
            reasoning: str | None = None
            enrichment_data: dict | None = None

        model = DetailModel(
            id=1,
            name="Test",
            llm_prompt="long prompt...",
            reasoning="long reasoning...",
            enrichment_data={"key": "value"},
        )
        result = serialize_for_list_view(model)

        assert "id" in result
        assert "name" in result
        assert "llm_prompt" not in result
        assert "reasoning" not in result
        assert "enrichment_data" not in result

    def test_excludes_custom_detail_fields(self):
        """Test exclusion of custom detail fields."""
        model = SampleModel(
            id=1,
            name="Test",
            created_at=datetime.now(UTC),
            large_field="large content",
        )
        result = serialize_for_list_view(model, detail_fields={"large_field"})

        assert "large_field" not in result
        assert "id" in result


class TestSerializeForDetailView:
    """Tests for serialize_for_detail_view function."""

    def test_includes_all_non_none_fields(self):
        """Test that all non-None fields are included."""
        model = SampleModel(
            id=1,
            name="Test",
            created_at=datetime.now(UTC),
            large_field="large content",
        )
        result = serialize_for_detail_view(model)

        assert "id" in result
        assert "name" in result
        assert "large_field" in result

    def test_excludes_none_fields(self):
        """Test that None fields are excluded."""
        model = SampleModel(
            id=1,
            name="Test",
            created_at=datetime.now(UTC),
            large_field=None,
        )
        result = serialize_for_detail_view(model)

        assert "large_field" not in result


class TestSerializationMixin:
    """Tests for SerializationMixin class."""

    def test_dump_for_list_excludes_detail_fields(self):
        """Test that dump_for_list excludes specified detail-only fields."""
        model = SampleMixinModel(
            id=1,
            name="Test",
            created_at=datetime.now(UTC),
            llm_prompt="long prompt...",
            reasoning="long reasoning...",
        )
        result = model.dump_for_list(exclude={"llm_prompt", "reasoning"})

        assert "id" in result
        assert "name" in result
        assert "llm_prompt" not in result
        assert "reasoning" not in result

    def test_dump_for_detail_includes_all_fields(self):
        """Test that dump_for_detail includes all non-None fields."""
        model = SampleMixinModel(
            id=1,
            name="Test",
            created_at=datetime.now(UTC),
            llm_prompt="long prompt...",
            reasoning="long reasoning...",
        )
        result = model.dump_for_detail()

        assert "id" in result
        assert "llm_prompt" in result
        assert "reasoning" in result

    def test_dump_json_fast_uses_json_mode(self):
        """Test that dump_json_fast produces JSON-compatible output."""
        model = SampleMixinModel(
            id=1,
            name="Test",
            created_at=datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC),
        )
        result = model.dump_json_fast()

        # Should be string, not datetime object
        assert isinstance(result["created_at"], str)
        assert result["created_at"] == "2025-01-15T12:00:00Z"


class TestJsonModeVsDefaultMode:
    """Tests comparing mode='json' vs default serialization."""

    def test_datetime_output_format(self):
        """Test that mode='json' produces ISO string while default produces datetime."""
        model = SampleModel(
            id=1,
            name="Test",
            created_at=datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC),
        )

        # Default mode - datetime remains as datetime
        default_result = model.model_dump()
        assert isinstance(default_result["created_at"], datetime)

        # JSON mode - datetime becomes string
        json_result = model.model_dump(mode="json")
        assert isinstance(json_result["created_at"], str)

    def test_enum_output_format(self):
        """Test that mode='json' produces string while default may produce enum."""
        model = SampleModel(
            id=1,
            name="Test",
            created_at=datetime.now(UTC),
            status=StatusEnum.ACTIVE,
        )

        # JSON mode - enum becomes string value
        json_result = model.model_dump(mode="json")
        assert json_result["status"] == "active"
        assert isinstance(json_result["status"], str)

    def test_json_mode_is_json_serializable(self):
        """Test that mode='json' output can be directly JSON serialized."""
        import json

        model = SampleModel(
            id=1,
            name="Test",
            created_at=datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC),
            status=StatusEnum.ACTIVE,
        )

        # JSON mode result should serialize without custom encoder
        json_result = model.model_dump(mode="json")
        serialized = json.dumps(json_result)

        # Should contain expected values
        assert "2025-01-15T12:00:00Z" in serialized
        assert '"active"' in serialized
