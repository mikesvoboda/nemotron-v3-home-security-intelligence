"""Unit tests for OpenAPI schema customization (NEM-3780).

This module tests custom OpenAPI schema generation with:
- Rich examples with realistic data
- Comprehensive field descriptions
- Proper type hints in generated schemas
- Model-level documentation
- Enum descriptions and examples
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

from backend.api.schemas.openapi_customization import (
    OpenAPISchemaConfig,
    create_openapi_model,
    with_openapi_example,
    with_openapi_examples,
)


class TestOpenAPISchemaConfig:
    """Tests for OpenAPISchemaConfig settings."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = OpenAPISchemaConfig()
        assert config.include_examples is True
        assert config.include_descriptions is True
        assert config.include_deprecated_flag is True

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = OpenAPISchemaConfig(
            include_examples=False,
            include_descriptions=False,
            include_deprecated_flag=False,
        )
        assert config.include_examples is False
        assert config.include_descriptions is False
        assert config.include_deprecated_flag is False


class TestWithOpenAPIExample:
    """Tests for with_openapi_example decorator."""

    def test_adds_example_to_model(self) -> None:
        """Test that decorator adds example to model schema."""

        @with_openapi_example({"name": "Test Camera", "status": "online"})
        class TestModel(BaseModel):
            name: str
            status: str

        schema = TestModel.model_json_schema()
        assert "example" in schema
        assert schema["example"]["name"] == "Test Camera"
        assert schema["example"]["status"] == "online"

    def test_preserves_existing_config(self) -> None:
        """Test that decorator preserves existing model config."""

        @with_openapi_example({"id": 1})
        class TestModel(BaseModel):
            model_config = {"str_strip_whitespace": True}
            id: int

        assert TestModel.model_config.get("str_strip_whitespace") is True
        schema = TestModel.model_json_schema()
        assert schema["example"]["id"] == 1

    def test_multiple_examples_override(self) -> None:
        """Test that applying decorator twice overrides example."""

        @with_openapi_example({"value": 2})
        @with_openapi_example({"value": 1})
        class TestModel(BaseModel):
            value: int

        schema = TestModel.model_json_schema()
        # Second decorator (outer) should win
        assert schema["example"]["value"] == 2


class TestWithOpenAPIExamples:
    """Tests for with_openapi_examples decorator (multiple examples)."""

    def test_adds_multiple_examples(self) -> None:
        """Test that decorator adds multiple named examples."""

        @with_openapi_examples(
            {
                "online_camera": {
                    "summary": "Online camera",
                    "value": {"name": "Front Door", "status": "online"},
                },
                "offline_camera": {
                    "summary": "Offline camera",
                    "value": {"name": "Garage", "status": "offline"},
                },
            }
        )
        class TestModel(BaseModel):
            name: str
            status: str

        schema = TestModel.model_json_schema()
        assert "examples" in schema
        assert "online_camera" in schema["examples"]
        assert "offline_camera" in schema["examples"]
        assert schema["examples"]["online_camera"]["value"]["status"] == "online"

    def test_examples_have_summaries(self) -> None:
        """Test that examples include summaries."""

        @with_openapi_examples(
            {
                "example1": {
                    "summary": "Example summary",
                    "description": "Detailed description",
                    "value": {"field": "value"},
                },
            }
        )
        class TestModel(BaseModel):
            field: str

        schema = TestModel.model_json_schema()
        assert schema["examples"]["example1"]["summary"] == "Example summary"
        assert schema["examples"]["example1"]["description"] == "Detailed description"


class TestCreateOpenAPIModel:
    """Tests for create_openapi_model factory function."""

    def test_creates_model_with_description(self) -> None:
        """Test that factory creates model with description."""
        Model = create_openapi_model(
            "CameraRequest",
            {
                "name": (str, Field(description="Camera name")),
                "status": (str, Field(default="online", description="Camera status")),
            },
            description="Request schema for creating a camera",
        )

        schema = Model.model_json_schema()
        assert schema["description"] == "Request schema for creating a camera"

    def test_creates_model_with_example(self) -> None:
        """Test that factory creates model with example."""
        Model = create_openapi_model(
            "CameraRequest",
            {
                "name": (str, Field(description="Camera name")),
            },
            example={"name": "Front Door Camera"},
        )

        schema = Model.model_json_schema()
        assert schema["example"]["name"] == "Front Door Camera"

    def test_creates_model_with_field_descriptions(self) -> None:
        """Test that factory creates model with field descriptions."""
        Model = create_openapi_model(
            "CameraRequest",
            {
                "name": (str, Field(description="Human-readable camera name")),
                "folder_path": (str, Field(description="File system path for uploads")),
            },
        )

        schema = Model.model_json_schema()
        assert schema["properties"]["name"]["description"] == "Human-readable camera name"
        assert schema["properties"]["folder_path"]["description"] == "File system path for uploads"

    def test_creates_model_with_title(self) -> None:
        """Test that factory creates model with custom title."""
        Model = create_openapi_model(
            "CameraCreateRequest",
            {"name": (str, Field())},
            title="Create Camera Request",
        )

        schema = Model.model_json_schema()
        assert schema["title"] == "Create Camera Request"

    def test_model_validation_works(self) -> None:
        """Test that created model validates correctly."""
        Model = create_openapi_model(
            "TestModel",
            {
                "name": (str, Field(min_length=1, max_length=100)),
                "count": (int, Field(ge=0, le=1000)),
            },
        )

        # Valid data
        instance = Model(name="Test", count=50)
        assert instance.name == "Test"
        assert instance.count == 50

        # Invalid data should raise
        with pytest.raises(Exception):  # ValidationError
            Model(name="", count=50)  # name too short


class TestEnhancedFieldDescriptions:
    """Tests for enhanced field descriptions in schemas."""

    def test_field_with_constraints_description(self) -> None:
        """Test that field constraints appear in schema."""

        class TestModel(BaseModel):
            """Test model for field constraints."""

            score: int = Field(
                ...,
                ge=0,
                le=100,
                description="Risk score from 0 (safe) to 100 (critical)",
                json_schema_extra={"example": 75},
            )

        schema = TestModel.model_json_schema()
        assert schema["properties"]["score"]["minimum"] == 0
        assert schema["properties"]["score"]["maximum"] == 100
        assert "example" in schema["properties"]["score"]

    def test_optional_field_description(self) -> None:
        """Test that optional fields are properly described."""

        class TestModel(BaseModel):
            """Test model for optional fields."""

            required_field: str = Field(description="This field is required")
            optional_field: str | None = Field(default=None, description="This field is optional")

        schema = TestModel.model_json_schema()
        assert "required_field" in schema["required"]
        assert "optional_field" not in schema.get("required", [])

    def test_deprecated_field_flag(self) -> None:
        """Test that deprecated fields have proper flag."""

        class TestModel(BaseModel):
            """Test model with deprecated field."""

            new_field: str = Field(description="Use this field")
            old_field: str | None = Field(
                default=None,
                description="Deprecated: Use new_field instead",
                deprecated=True,
            )

        schema = TestModel.model_json_schema()
        assert schema["properties"]["old_field"].get("deprecated") is True


class TestEnumSchemaEnhancement:
    """Tests for enum schema enhancements."""

    def test_enum_descriptions_in_schema(self) -> None:
        """Test that enum values have descriptions."""
        from enum import Enum

        class CameraStatus(str, Enum):
            """Camera operational status."""

            ONLINE = "online"
            OFFLINE = "offline"
            ERROR = "error"

        class TestModel(BaseModel):
            """Test model with enum field."""

            status: CameraStatus = Field(
                description="Current camera status",
                json_schema_extra={
                    "enum_descriptions": {
                        "online": "Camera is functioning normally",
                        "offline": "Camera is not responding",
                        "error": "Camera has encountered an error",
                    }
                },
            )

        schema = TestModel.model_json_schema()
        # Check enum reference exists in properties
        assert "status" in schema["properties"]
        # The actual enum values are in $defs for referenced enums
        # or directly in the property for inlined enums
        status_schema = schema["properties"]["status"]
        # Check that description is present
        assert status_schema.get("description") == "Current camera status"


class TestSchemaIntegration:
    """Integration tests for OpenAPI schema generation."""

    def test_complex_model_schema(self) -> None:
        """Test schema generation for complex nested model."""
        from datetime import datetime
        from typing import Any

        class DetectionData(BaseModel):
            """Detection enrichment data."""

            model_config = {
                "json_schema_extra": {"example": {"label": "person", "confidence": 0.95}}
            }

            label: str = Field(description="Detected object class")
            confidence: float = Field(ge=0.0, le=1.0, description="Detection confidence")
            metadata: dict[str, Any] | None = Field(
                default=None, description="Additional detection metadata"
            )

        class EventResponse(BaseModel):
            """Event response schema."""

            model_config = {
                "json_schema_extra": {
                    "example": {
                        "id": 12345,
                        "camera_id": "front_door",
                        "risk_score": 75,
                        "detections": [{"label": "person", "confidence": 0.95}],
                    }
                }
            }

            id: int = Field(description="Unique event identifier")
            camera_id: str = Field(description="Camera that captured the event")
            risk_score: int = Field(ge=0, le=100, description="Risk assessment score (0-100)")
            created_at: datetime = Field(description="When the event was created")
            detections: list[DetectionData] = Field(
                default_factory=list, description="Associated detections"
            )

        schema = EventResponse.model_json_schema()

        # Check main schema
        assert "example" in schema
        assert schema["example"]["id"] == 12345

        # Check nested schema reference
        assert "detections" in schema["properties"]

    def test_schema_with_refs(self) -> None:
        """Test that $ref schemas are properly generated."""

        class Address(BaseModel):
            """Physical address."""

            street: str
            city: str

        class Person(BaseModel):
            """Person with address."""

            name: str
            address: Address

        schema = Person.model_json_schema()

        # Schema should have definitions for nested models
        assert "$defs" in schema or "definitions" in schema
