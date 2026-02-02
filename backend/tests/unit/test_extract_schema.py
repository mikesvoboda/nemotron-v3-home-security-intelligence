"""Unit tests for extract_schema utility (NEM-5021).

Tests the schema extraction utility used for snapshot testing.
"""

from backend.tests.conftest import extract_schema


class TestExtractSchema:
    """Test suite for extract_schema utility function."""

    def test_extract_schema_simple_dict(self):
        """Test extraction from simple dictionary."""
        data = {"id": 123, "name": "test", "active": True}
        schema = extract_schema(data)

        assert schema == {"id": "int", "name": "str", "active": "bool"}

    def test_extract_schema_nested_dict(self):
        """Test extraction from nested dictionary."""
        data = {
            "id": 123,
            "metadata": {"location": "front_door", "floor": 1, "enabled": True},
        }
        schema = extract_schema(data)

        assert schema == {
            "id": "int",
            "metadata": {"location": "str", "floor": "int", "enabled": "bool"},
        }

    def test_extract_schema_list_default(self):
        """Test extraction from list uses first item as representative."""
        data = {"items": [{"id": 1, "name": "first"}, {"id": 2, "name": "second"}]}
        schema = extract_schema(data)

        # Should use first item as representative
        assert schema == {"items": [{"id": "int", "name": "str"}]}

    def test_extract_schema_list_preserve_lengths(self):
        """Test extraction preserves list lengths when requested."""
        data = {"items": [{"id": 1}, {"id": 2}, {"id": 3}]}
        schema = extract_schema(data, preserve_lengths=True)

        # Should preserve all items
        assert schema == {
            "items": [{"id": "int"}, {"id": "int"}, {"id": "int"}],
        }

    def test_extract_schema_empty_list(self):
        """Test extraction from empty list."""
        data = {"items": []}
        schema = extract_schema(data)

        assert schema == {"items": []}

    def test_extract_schema_none_value(self):
        """Test extraction handles None values."""
        data = {"id": 123, "notes": None}
        schema = extract_schema(data)

        assert schema == {"id": "int", "notes": "NoneType"}

    def test_extract_schema_primitive_types(self):
        """Test extraction handles all primitive types."""
        data = {
            "string": "text",
            "integer": 42,
            "float": 3.14,
            "boolean": True,
            "none": None,
        }
        schema = extract_schema(data)

        assert schema == {
            "string": "str",
            "integer": "int",
            "float": "float",
            "boolean": "bool",
            "none": "NoneType",
        }

    def test_extract_schema_complex_nested_structure(self):
        """Test extraction from complex nested structure."""
        data = {
            "id": 123,
            "cameras": [
                {
                    "id": "cam1",
                    "name": "Front Door",
                    "zones": [
                        {"id": 1, "name": "Entry"},
                        {"id": 2, "name": "Porch"},
                    ],
                    "metadata": {"location": "front", "floor": 1},
                }
            ],
            "stats": {"total": 10, "active": 5, "rate": 0.5},
        }
        schema = extract_schema(data)

        assert schema == {
            "id": "int",
            "cameras": [
                {
                    "id": "str",
                    "name": "str",
                    "zones": [{"id": "int", "name": "str"}],
                    "metadata": {"location": "str", "floor": "int"},
                }
            ],
            "stats": {"total": "int", "active": "int", "rate": "float"},
        }

    def test_extract_schema_list_of_primitives(self):
        """Test extraction from list of primitives."""
        data = {"tags": ["indoor", "front", "motion"]}
        schema = extract_schema(data)

        assert schema == {"tags": ["str"]}

    def test_extract_schema_mixed_list(self):
        """Test extraction from list with mixed types (uses first item)."""
        data = {"values": [1, 2, 3]}
        schema = extract_schema(data)

        assert schema == {"values": ["int"]}

    def test_extract_schema_api_response_structure(self):
        """Test extraction from realistic API response."""
        data = {
            "id": 123,
            "event_id": 456,
            "feedback_type": "false_positive",
            "notes": "Test notes",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
        schema = extract_schema(data)

        assert schema == {
            "id": "int",
            "event_id": "int",
            "feedback_type": "str",
            "notes": "str",
            "created_at": "str",
            "updated_at": "str",
        }

    def test_extract_schema_pagination_metadata(self):
        """Test extraction from pagination structure."""
        data = {
            "items": [{"id": 1}, {"id": 2}],
            "pagination": {
                "total": 100,
                "limit": 20,
                "offset": 0,
                "has_more": True,
            },
        }
        schema = extract_schema(data)

        assert schema == {
            "items": [{"id": "int"}],
            "pagination": {
                "total": "int",
                "limit": "int",
                "offset": "int",
                "has_more": "bool",
            },
        }

    def test_extract_schema_error_response(self):
        """Test extraction from error response structure."""
        data = {
            "detail": "Resource not found",
            "status_code": 404,
            "timestamp": "2024-01-01T00:00:00Z",
        }
        schema = extract_schema(data)

        assert schema == {
            "detail": "str",
            "status_code": "int",
            "timestamp": "str",
        }

    def test_extract_schema_top_level_list(self):
        """Test extraction when root is a list."""
        data = [{"id": 1, "name": "first"}, {"id": 2, "name": "second"}]
        schema = extract_schema(data)

        # Should use first item as representative
        assert schema == [{"id": "int", "name": "str"}]

    def test_extract_schema_top_level_list_preserve_lengths(self):
        """Test extraction preserves length for top-level list."""
        data = [{"id": 1}, {"id": 2}]
        schema = extract_schema(data, preserve_lengths=True)

        assert schema == [{"id": "int"}, {"id": "int"}]

    def test_extract_schema_deeply_nested(self):
        """Test extraction from deeply nested structure."""
        data = {
            "level1": {
                "level2": {
                    "level3": {
                        "level4": {"id": 1, "values": [1, 2, 3]},
                    },
                },
            },
        }
        schema = extract_schema(data)

        assert schema == {
            "level1": {
                "level2": {
                    "level3": {
                        "level4": {"id": "int", "values": ["int"]},
                    },
                },
            },
        }
