"""OpenAPI schema customization utilities (NEM-3780).

This module provides utilities for generating better OpenAPI schemas with:
- Rich examples with realistic data
- Comprehensive field descriptions
- Proper type hints in generated schemas
- Model-level documentation
- Enum descriptions and examples

Usage:
    from backend.api.schemas.openapi_customization import (
        OpenAPISchemaConfig,
        create_openapi_model,
        with_openapi_example,
        with_openapi_examples,
    )

    @with_openapi_example({"name": "Front Door", "status": "online"})
    class CameraResponse(BaseModel):
        name: str
        status: str

    # Or use the factory function for dynamic model creation
    Model = create_openapi_model(
        "CameraCreate",
        {"name": (str, Field(description="Camera name"))},
        example={"name": "Front Door"},
    )
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field, create_model

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = [
    "OpenAPISchemaConfig",
    "create_openapi_model",
    "with_openapi_example",
    "with_openapi_examples",
]

ModelT = TypeVar("ModelT", bound=type[BaseModel])


class OpenAPISchemaConfig(BaseModel):
    """Configuration for OpenAPI schema generation.

    Controls which features are included in generated OpenAPI schemas.

    Attributes:
        include_examples: Include example values in schemas
        include_descriptions: Include field descriptions in schemas
        include_deprecated_flag: Include deprecated flags for deprecated fields
    """

    model_config = ConfigDict(frozen=True)

    include_examples: bool = Field(
        default=True,
        description="Include example values in schemas",
    )
    include_descriptions: bool = Field(
        default=True,
        description="Include field descriptions in schemas",
    )
    include_deprecated_flag: bool = Field(
        default=True,
        description="Include deprecated flags for deprecated fields",
    )


def with_openapi_example(example: dict[str, Any]) -> Callable[[ModelT], ModelT]:
    """Decorator to add an OpenAPI example to a Pydantic model.

    Adds the provided example to the model's JSON schema, which appears
    in OpenAPI documentation.

    Args:
        example: Example data for the model

    Returns:
        Decorator function that adds the example to the model

    Example:
        @with_openapi_example({"name": "Front Door", "status": "online"})
        class CameraResponse(BaseModel):
            name: str
            status: str
    """

    def decorator(cls: ModelT) -> ModelT:
        # Get existing model config or create new one
        existing_config = getattr(cls, "model_config", {})
        # ConfigDict is a TypedDict, convert to regular dict
        existing_config = dict(existing_config) if existing_config else {}

        # Get existing json_schema_extra or create new one
        json_schema_extra = existing_config.get("json_schema_extra", {})
        if callable(json_schema_extra):
            # If it's a function, we can't merge, so wrap it
            original_func = json_schema_extra

            def new_schema_extra(schema: dict[str, Any]) -> None:
                schema["example"] = example
                original_func(schema)

            existing_config["json_schema_extra"] = new_schema_extra
        else:
            # Merge with existing dict
            json_schema_extra = dict(json_schema_extra) if json_schema_extra else {}
            json_schema_extra["example"] = example
            existing_config["json_schema_extra"] = json_schema_extra

        # Update the model config
        cls.model_config = ConfigDict(**existing_config)

        return cls

    return decorator


def with_openapi_examples(examples: dict[str, dict[str, Any]]) -> Callable[[ModelT], ModelT]:
    """Decorator to add multiple named OpenAPI examples to a Pydantic model.

    Adds multiple examples to the model's JSON schema, which appear in
    OpenAPI documentation as named examples.

    Args:
        examples: Dictionary of named examples, where each value contains:
            - summary: Brief description of the example
            - description: Detailed description (optional)
            - value: The example data

    Returns:
        Decorator function that adds the examples to the model

    Example:
        @with_openapi_examples({
            "online_camera": {
                "summary": "Online camera",
                "value": {"name": "Front Door", "status": "online"},
            },
            "offline_camera": {
                "summary": "Offline camera",
                "value": {"name": "Garage", "status": "offline"},
            },
        })
        class CameraResponse(BaseModel):
            name: str
            status: str
    """

    def decorator(cls: ModelT) -> ModelT:
        # Get existing model config or create new one
        existing_config = getattr(cls, "model_config", {})
        # ConfigDict is a TypedDict, convert to regular dict
        existing_config = dict(existing_config) if existing_config else {}

        # Get existing json_schema_extra or create new one
        json_schema_extra = existing_config.get("json_schema_extra", {})
        if callable(json_schema_extra):
            # If it's a function, we can't merge, so wrap it
            original_func = json_schema_extra

            def new_schema_extra(schema: dict[str, Any]) -> None:
                schema["examples"] = examples
                original_func(schema)

            existing_config["json_schema_extra"] = new_schema_extra
        else:
            # Merge with existing dict
            json_schema_extra = dict(json_schema_extra) if json_schema_extra else {}
            json_schema_extra["examples"] = examples
            existing_config["json_schema_extra"] = json_schema_extra

        # Update the model config
        cls.model_config = ConfigDict(**existing_config)

        return cls

    return decorator


def create_openapi_model(
    name: str,
    fields: dict[str, tuple[type, Any]],
    *,
    description: str | None = None,
    example: dict[str, Any] | None = None,
    examples: dict[str, dict[str, Any]] | None = None,
    title: str | None = None,
    base: type[BaseModel] | None = None,
) -> type[BaseModel]:
    """Factory function to create a Pydantic model with OpenAPI enhancements.

    Creates a Pydantic model dynamically with proper OpenAPI schema configuration,
    including descriptions, examples, and other metadata.

    Args:
        name: Name for the model class
        fields: Dictionary of field definitions, where each value is a tuple of
            (type, Field(...)) or just a type
        description: Model description for OpenAPI docs
        example: Single example for the model
        examples: Multiple named examples for the model
        title: Custom title for the model (defaults to name)
        base: Base class to inherit from (defaults to BaseModel)

    Returns:
        Dynamically created Pydantic model class

    Example:
        Model = create_openapi_model(
            "CameraCreate",
            {
                "name": (str, Field(description="Camera name")),
                "status": (str, Field(default="online", description="Status")),
            },
            description="Request schema for creating a camera",
            example={"name": "Front Door", "status": "online"},
        )
    """
    # Build json_schema_extra
    json_schema_extra: dict[str, Any] = {}
    if description:
        json_schema_extra["description"] = description
    if example:
        json_schema_extra["example"] = example
    if examples:
        json_schema_extra["examples"] = examples

    # Build model config
    model_config: dict[str, Any] = {}
    if json_schema_extra:
        model_config["json_schema_extra"] = json_schema_extra
    if title:
        model_config["title"] = title

    # Prepare field definitions for create_model: {"field_name": (type, FieldInfo) or type}
    field_definitions: dict[str, Any] = {}
    for field_name, field_def in fields.items():
        if isinstance(field_def, tuple) and len(field_def) == 2:
            field_type, field_info = field_def
            field_definitions[field_name] = (field_type, field_info)
        else:
            # Just a type, no Field info
            field_definitions[field_name] = (field_def, ...)

    # Create the model
    base_class = base or BaseModel
    model = create_model(
        name,
        __base__=base_class,
        __module__=__name__,
        **field_definitions,
    )

    # Apply model config
    if model_config:
        # Handle json_schema_extra specially to include description
        existing_config = getattr(model, "model_config", {})
        # ConfigDict is a TypedDict, convert to regular dict
        existing_config = dict(existing_config) if existing_config else {}

        # Merge json_schema_extra
        existing_extra = existing_config.get("json_schema_extra", {})
        if isinstance(existing_extra, dict):
            merged_extra = {**existing_extra, **json_schema_extra}
        else:
            merged_extra = json_schema_extra

        existing_config["json_schema_extra"] = merged_extra

        if title:
            existing_config["title"] = title

        model.model_config = ConfigDict(**existing_config)

    return model
