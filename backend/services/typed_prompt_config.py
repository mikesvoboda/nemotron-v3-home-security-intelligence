"""Type-safe prompt configuration with generic constraints.

This module provides type-safe prompt templates using Python generics and Pydantic
models. It ensures compile-time type checking (via mypy) and runtime validation
for all prompt parameters.

Usage:
    from backend.services.typed_prompt_config import (
        TypedPromptTemplate,
        NemotronPromptParams,
        create_typed_template,
        get_typed_params,
    )

    # Create a typed template
    template = TypedPromptTemplate[NemotronPromptParams](
        model_name="nemotron",
        template_string="Camera: {camera_name}",
        param_type=NemotronPromptParams,
    )

    # Or use the factory
    template = create_typed_template("nemotron", "Camera: {camera_name}")

    # Validate and use params
    params = NemotronPromptParams(
        camera_name="Front Door",
        timestamp="2024-01-15T10:30:00",
        day_of_week="Monday",
        time_of_day="morning",
    )
    rendered = template.render(params)

NEM-1547: Type-safe prompt configuration with generic constraints
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# =============================================================================
# Base Class for All Prompt Parameters
# =============================================================================


class PromptParamBase(BaseModel):
    """Base class for all prompt parameter types.

    All model-specific prompt parameter classes should inherit from this base.
    This enables generic constraints and type checking at both compile time
    (via mypy) and runtime.
    """

    model_config = ConfigDict(
        frozen=True,  # Immutable after creation
        extra="forbid",  # Reject unknown fields
        str_strip_whitespace=True,  # Auto-strip whitespace from strings
    )


# =============================================================================
# Model-Specific Prompt Parameter Types
# =============================================================================


class NemotronPromptParams(PromptParamBase):
    """Parameters for Nemotron risk analysis prompts.

    These parameters are used to render the system prompt template for
    the Nemotron LLM-based risk analyzer.
    """

    # Required fields
    camera_name: str = Field(..., min_length=1, description="Name of the camera")
    timestamp: str = Field(..., min_length=1, description="Timestamp of the event")
    day_of_week: str = Field(..., min_length=1, description="Day of the week")
    time_of_day: str = Field(
        ..., min_length=1, description="Time of day (morning/afternoon/evening/night)"
    )

    # Optional enrichment fields
    zone_analysis: str | None = Field(None, description="Zone analysis information")
    baseline_comparison: str | None = Field(None, description="Baseline comparison data")
    deviation_score: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Deviation score from baseline (0-1)",
    )
    cross_camera_summary: str | None = Field(None, description="Cross-camera correlation summary")
    detections_list: str | None = Field(None, description="Formatted list of detections")
    reid_context: str | None = Field(None, description="Person re-identification context")
    scene_analysis: str | None = Field(None, description="Scene analysis from Florence-2")

    @field_validator("camera_name")
    @classmethod
    def validate_camera_name_not_whitespace(cls, v: str) -> str:
        """Ensure camera_name is not just whitespace."""
        if not v.strip():
            raise ValueError("camera_name cannot be empty or whitespace only")
        return v


class Florence2PromptParams(PromptParamBase):
    """Parameters for Florence-2 VQA prompts.

    These parameters configure the visual question answering queries
    for the Florence-2 scene analysis model.
    """

    queries: list[str] = Field(
        ...,
        min_length=1,
        description="List of VQA queries for scene analysis",
    )

    @field_validator("queries")
    @classmethod
    def validate_queries_not_empty_strings(cls, v: list[str]) -> list[str]:
        """Ensure queries list doesn't contain empty strings."""
        if any(not q.strip() for q in v):
            raise ValueError("queries cannot contain empty or whitespace-only strings")
        return v


class YoloWorldPromptParams(PromptParamBase):
    """Parameters for YOLO-World object detection prompts.

    These parameters configure the custom object classes and thresholds
    for the YOLO-World detector.
    """

    classes: list[str] = Field(
        ...,
        min_length=1,
        description="Custom object classes to detect",
    )
    confidence_threshold: float = Field(
        0.35,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for detections",
    )

    @field_validator("classes")
    @classmethod
    def validate_classes_not_empty_strings(cls, v: list[str]) -> list[str]:
        """Ensure classes list doesn't contain empty strings."""
        if any(not c.strip() for c in v):
            raise ValueError("classes cannot contain empty or whitespace-only strings")
        return v


class XClipPromptParams(PromptParamBase):
    """Parameters for X-CLIP action recognition prompts.

    These parameters configure the action classes for temporal
    activity recognition.
    """

    action_classes: list[str] = Field(
        ...,
        min_length=1,
        description="Action classes to recognize",
    )

    @field_validator("action_classes")
    @classmethod
    def validate_action_classes_not_empty_strings(cls, v: list[str]) -> list[str]:
        """Ensure action_classes list doesn't contain empty strings."""
        if any(not a.strip() for a in v):
            raise ValueError("action_classes cannot contain empty or whitespace-only strings")
        return v


class FashionClipPromptParams(PromptParamBase):
    """Parameters for Fashion-CLIP clothing analysis prompts.

    These parameters configure clothing categories and suspicious
    indicators for attire analysis.
    """

    clothing_categories: list[str] = Field(
        ...,
        min_length=1,
        description="Clothing categories to classify",
    )
    suspicious_indicators: list[str] = Field(
        default_factory=list,
        description="Suspicious clothing indicators to look for",
    )

    @field_validator("clothing_categories")
    @classmethod
    def validate_categories_not_empty_strings(cls, v: list[str]) -> list[str]:
        """Ensure clothing_categories list doesn't contain empty strings."""
        if any(not c.strip() for c in v):
            raise ValueError("clothing_categories cannot contain empty or whitespace-only strings")
        return v


# =============================================================================
# Generic Template with Python 3.12+ Type Parameters
# =============================================================================


class TypedPromptTemplate[T: PromptParamBase]:
    """A type-safe prompt template with generic parameter constraints.

    This class provides compile-time (mypy) and runtime type checking
    for prompt parameters. The generic type parameter T must be a
    subclass of PromptParamBase.

    Example:
        template = TypedPromptTemplate[NemotronPromptParams](
            model_name="nemotron",
            template_string="Camera: {camera_name}",
            param_type=NemotronPromptParams,
        )

        # mypy will catch type errors:
        # template.validate_params(Florence2PromptParams(...))  # Error!
    """

    def __init__(
        self,
        model_name: str,
        template_string: str,
        param_type: type[T],
    ) -> None:
        """Initialize a typed prompt template.

        Args:
            model_name: Name of the AI model this template is for
            template_string: The prompt template string with {field} placeholders
            param_type: The Pydantic model class for validating parameters
        """
        self._model_name = model_name
        self._template_string = template_string
        self._param_type = param_type

    @property
    def model_name(self) -> str:
        """Get the model name."""
        return self._model_name

    @property
    def param_type(self) -> type[T]:
        """Get the parameter type class."""
        return self._param_type

    def validate_params(self, params: T) -> T:
        """Validate that parameters are of the correct type.

        Args:
            params: The parameters to validate

        Returns:
            The validated parameters

        Raises:
            TypeError: If params is not an instance of the expected type
        """
        if not isinstance(params, self._param_type):
            raise TypeError(f"Expected {self._param_type.__name__}, got {type(params).__name__}")
        return params

    def render(self, params: T) -> str:
        """Render the template with the given parameters.

        Args:
            params: Validated parameters for rendering

        Returns:
            The rendered prompt string
        """
        self.validate_params(params)

        # Convert params to dict for string formatting
        params_dict = params.model_dump()

        # Handle None values by converting to empty string
        for key, value in params_dict.items():
            if value is None:
                params_dict[key] = ""

        return self._template_string.format(**params_dict)


# =============================================================================
# Model Configuration Registry
# =============================================================================

# Maps model names to their parameter types
_MODEL_PARAM_REGISTRY: dict[str, type[PromptParamBase]] = {
    "nemotron": NemotronPromptParams,
    "florence2": Florence2PromptParams,
    "yolo_world": YoloWorldPromptParams,
    "xclip": XClipPromptParams,
    "fashion_clip": FashionClipPromptParams,
}


def get_param_type_for_model(model_name: str) -> type[PromptParamBase]:
    """Get the parameter type class for a given model.

    Args:
        model_name: Name of the AI model

    Returns:
        The Pydantic model class for the model's parameters

    Raises:
        KeyError: If the model name is not recognized
    """
    if model_name not in _MODEL_PARAM_REGISTRY:
        raise KeyError(f"Unknown model: {model_name}")
    return _MODEL_PARAM_REGISTRY[model_name]


def create_typed_template(
    model_name: str,
    template_string: str,
) -> TypedPromptTemplate[PromptParamBase]:
    """Factory function to create a typed template for a model.

    This function looks up the appropriate parameter type based on
    the model name and creates a TypedPromptTemplate instance.

    Args:
        model_name: Name of the AI model
        template_string: The prompt template string

    Returns:
        A TypedPromptTemplate instance configured for the model

    Raises:
        KeyError: If the model name is not recognized
    """
    param_type = get_param_type_for_model(model_name)
    return TypedPromptTemplate(
        model_name=model_name,
        template_string=template_string,
        param_type=param_type,
    )


def get_typed_params(
    model_name: str,
    raw_data: dict[str, Any],
) -> PromptParamBase:
    """Parse and validate raw data into typed parameters.

    This function provides a type-safe way to convert raw dictionaries
    (e.g., from JSON) into validated Pydantic models.

    Args:
        model_name: Name of the AI model
        raw_data: Raw dictionary data to validate

    Returns:
        A validated Pydantic model instance

    Raises:
        KeyError: If the model name is not recognized
        ValidationError: If the data fails validation
    """
    param_type = get_param_type_for_model(model_name)
    return param_type(**raw_data)


# =============================================================================
# Type Aliases for Improved Code Readability
# =============================================================================

# These type aliases can be used in function signatures for clarity
NemotronTemplate = TypedPromptTemplate[NemotronPromptParams]
Florence2Template = TypedPromptTemplate[Florence2PromptParams]
YoloWorldTemplate = TypedPromptTemplate[YoloWorldPromptParams]
XClipTemplate = TypedPromptTemplate[XClipPromptParams]
FashionClipTemplate = TypedPromptTemplate[FashionClipPromptParams]


# =============================================================================
# Export All Public Names
# =============================================================================

__all__ = [
    "FashionClipPromptParams",
    "FashionClipTemplate",
    "Florence2PromptParams",
    "Florence2Template",
    "NemotronPromptParams",
    "NemotronTemplate",
    "PromptParamBase",
    "TypedPromptTemplate",
    "XClipPromptParams",
    "XClipTemplate",
    "YoloWorldPromptParams",
    "YoloWorldTemplate",
    "create_typed_template",
    "get_param_type_for_model",
    "get_typed_params",
]
