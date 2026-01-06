"""Pydantic schemas for prompt management API endpoints."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AIModelEnum(str, Enum):
    """Supported AI models for prompt configuration."""

    NEMOTRON = "nemotron"
    FLORENCE2 = "florence2"
    YOLO_WORLD = "yolo_world"
    XCLIP = "xclip"
    FASHION_CLIP = "fashion_clip"


class NemotronConfig(BaseModel):
    """Configuration for Nemotron risk analysis model."""

    system_prompt: str = Field(..., min_length=1, description="Full system prompt template")
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Temperature for LLM generation (0-2)",
    )
    max_tokens: int = Field(
        default=2048,
        ge=1,
        le=16384,
        description="Maximum tokens for LLM response",
    )
    version: int | None = Field(None, description="Version number")

    @field_validator("system_prompt")
    @classmethod
    def validate_system_prompt_not_whitespace(cls, v: str) -> str:
        """Ensure system_prompt is not just whitespace."""
        if not v.strip():
            raise ValueError("system_prompt cannot be empty or whitespace only")
        return v


class Florence2Config(BaseModel):
    """Configuration for Florence-2 scene analysis model."""

    vqa_queries: list[str] = Field(
        ...,
        min_length=1,
        description="List of VQA queries for scene analysis",
    )

    @field_validator("vqa_queries")
    @classmethod
    def validate_queries_not_empty_strings(cls, v: list[str]) -> list[str]:
        """Ensure queries list doesn't contain empty strings."""
        if any(not q.strip() for q in v):
            raise ValueError("vqa_queries cannot contain empty or whitespace-only strings")
        return v


class YoloWorldConfig(BaseModel):
    """Configuration for YOLO-World custom object detection."""

    object_classes: list[str] = Field(
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

    @field_validator("object_classes")
    @classmethod
    def validate_classes_not_empty_strings(cls, v: list[str]) -> list[str]:
        """Ensure classes list doesn't contain empty strings."""
        if any(not c.strip() for c in v):
            raise ValueError("object_classes cannot contain empty or whitespace-only strings")
        return v


class XClipConfig(BaseModel):
    """Configuration for X-CLIP action recognition model."""

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


class FashionClipConfig(BaseModel):
    """Configuration for Fashion-CLIP clothing analysis model."""

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


def validate_config_for_model(model: AIModelEnum, config: dict[str, Any]) -> list[str]:
    """Validate configuration dictionary for a specific model.

    Args:
        model: The AI model type
        config: Configuration dictionary to validate

    Returns:
        List of validation error messages (empty if valid)
    """
    errors: list[str] = []

    # Map models to their config schemas and required fields
    validators: dict[AIModelEnum, tuple[type[BaseModel], dict[str, str]]] = {
        AIModelEnum.NEMOTRON: (NemotronConfig, {"system_prompt": "system_prompt"}),
        AIModelEnum.FLORENCE2: (Florence2Config, {"vqa_queries": "vqa_queries"}),
        AIModelEnum.YOLO_WORLD: (YoloWorldConfig, {"object_classes": "object_classes"}),
        AIModelEnum.XCLIP: (XClipConfig, {"action_classes": "action_classes"}),
        AIModelEnum.FASHION_CLIP: (
            FashionClipConfig,
            {"clothing_categories": "clothing_categories"},
        ),
    }

    if model not in validators:
        errors.append(f"Unknown model: {model}")
        return errors

    schema_class, required_fields = validators[model]

    # Check required fields first
    for _field_name, config_key in required_fields.items():
        if config_key not in config:
            errors.append(f"Missing required field: {config_key}")

    # If required fields are present, try full validation
    if not errors:
        try:
            schema_class(**config)
        except Exception as e:
            error_msg = str(e)
            # Extract just the error message from Pydantic's verbose output
            if "validation error" in error_msg.lower():
                # Parse Pydantic v2 error format
                for line in error_msg.split("\n"):
                    if (
                        line.strip()
                        and not line.startswith(" ")
                        and "validation error" not in line.lower()
                    ):
                        errors.append(line.strip())
                if not errors:
                    errors.append(error_msg)
            else:
                errors.append(error_msg)

    return errors


class ModelPromptConfig(BaseModel):
    """Configuration for a specific AI model."""

    model_config = ConfigDict(from_attributes=True)

    model: AIModelEnum
    config: dict[str, Any] = Field(..., description="Model-specific configuration")
    version: int = Field(..., description="Version number of this configuration")
    created_at: datetime | None = Field(None, description="When this version was created")
    created_by: str | None = Field(None, description="Who created this version")
    change_description: str | None = Field(None, description="Description of changes")


class AllPromptsResponse(BaseModel):
    """Response containing prompts for all configurable models."""

    version: str = Field("1.0", description="Export format version")
    exported_at: datetime = Field(..., description="Export timestamp")
    prompts: dict[str, dict[str, Any]] = Field(..., description="Configuration for each model")


class PromptUpdateRequest(BaseModel):
    """Request to update a model's prompt configuration.

    Supports optimistic locking via expected_version field to prevent
    race conditions when multiple clients update simultaneously.
    """

    config: dict[str, Any] = Field(..., description="New configuration for the model")
    change_description: str | None = Field(None, description="Optional description of what changed")
    expected_version: int | None = Field(
        None,
        description=(
            "Expected current version for optimistic locking. "
            "If provided, the update will fail with 409 Conflict if the current version "
            "doesn't match, indicating someone else updated the config concurrently."
        ),
        ge=1,
    )

    @field_validator("config")
    @classmethod
    def validate_config_not_empty(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Ensure config is not empty."""
        if not v:
            raise ValueError("Configuration cannot be empty")
        return v


class PromptVersionConflictError(Exception):
    """Exception raised when a concurrent modification is detected.

    This occurs when using optimistic locking and the expected_version
    doesn't match the current version in the database.
    """

    def __init__(self, model: str, expected_version: int, actual_version: int):
        self.model = model
        self.expected_version = expected_version
        self.actual_version = actual_version
        super().__init__(
            f"Concurrent modification detected for model '{model}': "
            f"expected version {expected_version}, but current version is {actual_version}. "
            f"Please refresh and retry your update."
        )


class PromptTestRequest(BaseModel):
    """Request to test a prompt with modified configuration."""

    model: AIModelEnum = Field(..., description="Model to test")
    config: dict[str, Any] = Field(..., description="Configuration to test")
    event_id: int | None = Field(None, description="Optional event ID to test against")
    image_path: str | None = Field(None, description="Optional image path to test with")


class PromptTestResult(BaseModel):
    """Result of a prompt test."""

    model: AIModelEnum
    before_score: int | None = Field(None, description="Risk score before changes")
    after_score: int | None = Field(None, description="Risk score after changes")
    before_response: dict[str, Any] | None = Field(None, description="Full response before changes")
    after_response: dict[str, Any] | None = Field(None, description="Full response after changes")
    improved: bool | None = Field(None, description="Whether the change improved results")
    test_duration_ms: int = Field(..., description="Test duration in milliseconds")
    error: str | None = Field(None, description="Error message if test failed")


class PromptVersionInfo(BaseModel):
    """Information about a single prompt version."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    model: AIModelEnum
    version: int
    created_at: datetime
    created_by: str | None
    change_description: str | None
    is_active: bool


class PromptHistoryResponse(BaseModel):
    """Response containing version history for prompts."""

    versions: list[PromptVersionInfo]
    total_count: int


class PromptRestoreRequest(BaseModel):
    """Request to restore a specific version."""

    pass


class PromptRestoreResponse(BaseModel):
    """Response after restoring a prompt version."""

    restored_version: int
    model: AIModelEnum
    new_version: int = Field(..., description="The new active version number")
    message: str


class PromptsExportResponse(BaseModel):
    """Export of all prompt configurations."""

    version: str = Field("1.0", description="Export format version")
    exported_at: datetime
    prompts: dict[str, dict[str, Any]] = Field(..., description="All model configurations")


class PromptsImportRequest(BaseModel):
    """Request to import prompt configurations."""

    version: str = Field("1.0", description="Import format version")
    prompts: dict[str, dict[str, Any]] = Field(..., description="Model configurations to import")

    @field_validator("prompts")
    @classmethod
    def validate_prompts_not_empty(cls, v: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Ensure prompts dict is not empty."""
        if not v:
            raise ValueError("Prompts configuration cannot be empty")
        return v


class PromptsImportResponse(BaseModel):
    """Response after importing prompt configurations."""

    imported_models: list[str]
    skipped_models: list[str] = Field(default_factory=list)
    new_versions: dict[str, int] = Field(
        ..., description="New version numbers for each imported model"
    )
    message: str


class PromptDiffEntry(BaseModel):
    """Diff entry for a single model's configuration."""

    model: str = Field(..., description="Model name")
    has_changes: bool = Field(..., description="Whether there are changes")
    current_version: int | None = Field(None, description="Current version number")
    current_config: dict[str, Any] | None = Field(None, description="Current configuration")
    imported_config: dict[str, Any] = Field(..., description="Configuration to import")
    changes: list[str] = Field(
        default_factory=list,
        description="List of human-readable change descriptions",
    )


class PromptsImportPreviewRequest(BaseModel):
    """Request to preview prompt configuration import without applying."""

    version: str = Field("1.0", description="Import format version")
    prompts: dict[str, dict[str, Any]] = Field(..., description="Model configurations to preview")

    @field_validator("prompts")
    @classmethod
    def validate_prompts_not_empty(cls, v: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Ensure prompts dict is not empty."""
        if not v:
            raise ValueError("Prompts configuration cannot be empty")
        return v


class PromptsImportPreviewResponse(BaseModel):
    """Response with preview of import changes."""

    version: str = Field(..., description="Import format version")
    valid: bool = Field(..., description="Whether the import data is valid")
    validation_errors: list[str] = Field(
        default_factory=list, description="List of validation errors"
    )
    diffs: list[PromptDiffEntry] = Field(
        default_factory=list, description="Diff entries for each model"
    )
    total_changes: int = Field(0, description="Total number of models with changes")
    unknown_models: list[str] = Field(default_factory=list, description="Models not recognized")
